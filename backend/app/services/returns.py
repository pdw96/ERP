"""구매반품 한 건을 받는다 — 공급사에 돌려보낸 것을 적는다.

**반품은 검사를 가리킨다.** 검사 응답의 `inspection_id` 가 그 손잡이이고, 공급사 ·
품목 · 로트는 거기서 따라간다(`PurchaseReturn` 의 「언제나 검사를 가리킨다」). 부르는
쪽이 로트를 따로 보내면 그 둘이 같은 것을 가리키는지 다시 물어야 하고, 검사 하나에
로트는 많아야 하나라(`uq_lot_inspection`) 보낼 까닭이 없다.

- **재고가 된 로트**(합격 · 특채) — 반품 문서와 원장의 구매반품출고 한 줄이 함께 선다.
  왜 돌려보내는지는 사람이 적는다
- **불합격분** — 재고가 된 적이 없으므로 원장 줄이 없다(원칙 ①). 왜 돌려보내는지는
  그 검사가 이미 들고 있다

### 한 트랜잭션이다

문서와 원장 줄이 함께 서거나 함께 없다. 데이터베이스도 커밋할 때 묻지만
(`purchase_return_has_its_ledger_line`) 거기서 나오는 말은 트리거의 말이라, 쓰기
경로는 그 둘을 처음부터 같이 넣는다.

### 데이터베이스가 막는 것을 먼저 이름으로 막는다

잔량과 불합격분의 합은 트리거가 지킨다(ADR 0013). 여기서 같은 것을 먼저 묻는 것은
**검사원이 제약 이름 대신 까닭을 받게** 하려는 것이고, 지키는 것은 여전히 트리거다 —
이 가드들을 지워도 데이터는 틀리지 않는다. 그래서 **트리거와 같은 순서로 잠근다**
(검사 줄 → 로트 줄). 묻는 순간과 넣는 순간 사이에 남이 끼면 이름 대신 500 이
나가고, 순서가 다르면 교착이 난다.

**이 경로가 못 보는 부류**(W-6 ③) —

- **같은 반품을 두 번 보내는 것.** 둘 다 선다 — 잔량이 남아 있으면 같은 물건을 두 번
  뺀다. 검사 쪽 NC-67 과 같은 자리이고, 잘못 선 줄을 상쇄하는 길이 범위 밖이라
  (`PRD.md` 「하지 않을 일」 5) 같은 기한까지 열어 둔다
- **판정 · 입고보다 앞선 반품 시각.** 시각을 서버가 지금으로 적으므로 이 경로에서는
  나지 않는다. 시계가 거꾸로 가면 트리거가 막고, 그 말은 500 이다
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Float, Numeric, case, cast, func, literal, select
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import NonconformityStageRule, TxnTypeAttribute
from app.db.common_codes import CommonCode
from app.db.inspection import Inspection
from app.db.inventory import Lot, PurchaseReturn, StockLedgerEntry


class RefusedReturn(Exception):
    """받을 수 없는 반품 — 무엇이 왜 막혔는지 이름으로 말한다.

    모양은 `RefusedInspection` 과 같다 — 사람에게 하는 말(메시지)과 기계에게 하는
    말(`code`)을 함께 든다. 메시지는 고쳐도 되고 `code` 는 고치면 깨진다.
    """

    def __init__(self, code: "ReturnRefusal", message: str) -> None:
        super().__init__(message)
        self.code = code


class ReturnRefusal(StrEnum):
    """반품을 거절할 때 `detail[].type` 으로 나가는 이름 — **목록이 여기 한 벌이다.**

    검사의 `Refusal` 과 **열거를 나눈다.** 한 열거로 합치면 두 경로의 422 가 같은
    목록을 스펙에 싣고, 검사를 부르는 쪽은 **검사에서는 날 수 없는 이름**까지 분기로
    적어야 한다. 이름 공간은 하나(업무 규칙)이고 열거가 경로마다 하나다.
    """

    UNKNOWN_INSPECTION = "unknown_inspection"
    UNKNOWN_SETTLE_TYPE = "unknown_settle_type"
    REASON_IS_MISSING = "reason_is_missing"
    REASON_COMES_WITH_A_FAILED_INSPECTION = "reason_comes_with_a_failed_inspection"
    REASON_IS_NOT_USABLE_AT_THIS_GATE = "reason_is_not_usable_at_this_gate"
    MORE_THAN_THE_LOT_HOLDS = "more_than_the_lot_holds"
    MORE_THAN_WAS_REJECTED = "more_than_was_rejected"


@dataclass(frozen=True)
class IncomingReturn:
    """받은 반품 한 건 — 어느 판정으로 들어온 것을 · 얼마나 · 어떻게 정산하고 · 누가."""

    inspection_id: int
    settle_type: str
    quantity: float
    returned_by: str
    # 왜 돌려보내는가. **재고 로트를 돌려보낼 때만** 적는다 — 불합격분은 검사가 든다.
    nonconformity_code: str | None = None


@dataclass(frozen=True)
class Returned:
    """반품이 선 뒤 남은 것."""

    purchase_return_id: int
    ledger_entry_id: int | None


def _inspection(session: Session, inspection_id: int) -> Inspection:
    """**그 검사 줄을 잠근다** — 반품 문서의 트리거가 맨 먼저 잡는 줄이다.

    같은 검사를 가리키는 두 반품이 여기서 줄을 선다. 잠그지 않고 물으면 둘이 같은
    합을 보고, 뒤엣것은 이름 대신 트리거의 500 을 받는다.
    """
    # `key_share=True` 가 `FOR NO KEY UPDATE` 다 — 트리거와 같은 잠금이고, 문서를 넣을
    # 때 외래키가 잡는 `KEY SHARE` 와 부딪치지 않는다(`ledger_guards.py` 머리).
    inspection = session.scalars(
        select(Inspection).where(Inspection.id == inspection_id).with_for_update(key_share=True)
    ).one_or_none()
    if inspection is None:
        raise RefusedReturn(
            ReturnRefusal.UNKNOWN_INSPECTION, f"그런 검사가 없다: {inspection_id}"
        )
    return inspection


def _must_be_a_settle_type(session: Session, settle_type: str) -> None:
    if session.get(CommonCode, (codes.SETTLE_TYPE, settle_type)) is None:
        raise RefusedReturn(
            ReturnRefusal.UNKNOWN_SETTLE_TYPE, f"그런 정산 구분이 없다: {settle_type}"
        )


def _must_be_a_reason_for_this_gate(session: Session, reason_code: str) -> None:
    """반품이 가리키는 검사의 단계(IQC)에서 쓸 수 있는 사유여야 한다.

    문서의 외래키가 `(사유 × 단계)` 규칙 표를 가리키므로 같은 것을 먼저 묻는다.
    **사람이 보는 항목인가는 묻지 않는다** — 검사에서는 재는 항목의 사유를 측정값만
    내게 했지만(원칙 ③), 반품은 판정이 아니라 **판정 뒤에 드러난 사실**이다. 창고에서
    다시 잰 입도가 벗어났으면 그 사유로 돌려보낸다.
    """
    rule = session.get(
        NonconformityStageRule,
        (codes.NC_REASON, reason_code, codes.INSP_STAGE, codes.STAGE_INCOMING),
    )
    if rule is None:
        raise RefusedReturn(
            ReturnRefusal.REASON_IS_NOT_USABLE_AT_THIS_GATE,
            f"관문 1 에서 쓸 수 있는 사유가 아니다: {reason_code}",
        )


def _as_counted(quantity: float) -> object:
    """**트리거가 세는 자릿수로 옮긴다.** `double precision` 으로 빼면 100 − 33.3 − 66.7
    이 0 이 아니라 −1.4e-14 쯤이 되어, 트리거는 받는 것을 여기서 거절한다."""
    return cast(literal(quantity, Float), Numeric)


def _lot_would_go_below_zero(session: Session, lot: Lot, quantity: float) -> bool:
    """**로트 줄을 잠근 뒤에** 그 로트의 원장 합을 센다 — 원장 트리거와 같은 셈이다.

    방향은 원장 줄에 없고 유형이 말한다(`total_effect`). 그 셈을 여기 다시 적는
    것은 거절의 이름을 위한 것이고, 틀려도 트리거가 막는다.
    """
    session.execute(select(Lot.id).where(Lot.id == lot.id).with_for_update(key_share=True))
    signed = case(
        (
            TxnTypeAttribute.total_effect == codes.EFFECT_INCREASE,
            cast(StockLedgerEntry.quantity, Numeric),
        ),
        (
            TxnTypeAttribute.total_effect == codes.EFFECT_DECREASE,
            -cast(StockLedgerEntry.quantity, Numeric),
        ),
    )
    balance = (
        select(func.coalesce(func.sum(signed), 0))
        .join(
            TxnTypeAttribute,
            (TxnTypeAttribute.group_code == StockLedgerEntry.txn_type_group)
            & (TxnTypeAttribute.code == StockLedgerEntry.txn_type),
        )
        .where(StockLedgerEntry.lot_id == lot.id)
        .scalar_subquery()
    )
    return bool(session.scalar(select(balance - _as_counted(quantity) < 0)))


def _rejected_would_be_exceeded(
    session: Session, inspection: Inspection, quantity: float
) -> bool:
    """불합격분은 원장 밖이라 **반품 문서끼리의 합**을 센다 — 반품 문서 트리거와 같은 셈이다.

    검사 줄은 `_inspection()` 이 이미 잠갔다.
    """
    returned = (
        select(func.coalesce(func.sum(cast(PurchaseReturn.quantity, Numeric)), 0))
        .where(PurchaseReturn.inspection_id == inspection.id, PurchaseReturn.lot_id.is_(None))
        .scalar_subquery()
    )
    return bool(
        session.scalar(
            select(returned + _as_counted(quantity) > _as_counted(inspection.quantity))
        )
    )


def return_to_supplier(session: Session, request: IncomingReturn) -> Returned:
    """반품 한 건을 받아 문서를 세우고, 재고 로트면 원장에서 뺀다.

    **부르는 쪽이 트랜잭션을 연다.** `receive()` 와 같이 `flush` 까지만 한다.
    """
    inspection = _inspection(session, request.inspection_id)
    _must_be_a_settle_type(session, request.settle_type)

    failed = inspection.result == codes.JUDGMENT_FAILED
    lot: Lot | None = None
    if failed:
        if request.nonconformity_code is not None:
            # **같은 사실을 두 곳에 적지 않는다**(원칙 ⑥). 그 검사가 사유를 이미 들고
            # 있고, 다른 사유를 받아 두면 「왜 돌려보냈나」가 두 답을 갖는다.
            raise RefusedReturn(
                ReturnRefusal.REASON_COMES_WITH_A_FAILED_INSPECTION,
                f"검사 {inspection.id} 는 불합격이라 사유({inspection.nonconformity_code})를"
                " 이미 들고 있다 — 반품에 다시 적지 않는다",
            )
        if _rejected_would_be_exceeded(session, inspection, request.quantity):
            raise RefusedReturn(
                ReturnRefusal.MORE_THAN_WAS_REJECTED,
                f"검사 {inspection.id} 에서 받은 것({inspection.quantity})보다 많이"
                " 돌려보내게 된다 — 앞서 돌려보낸 것까지 센다",
            )
    else:
        if request.nonconformity_code is None:
            raise RefusedReturn(
                ReturnRefusal.REASON_IS_MISSING,
                f"검사 {inspection.id} 는 {inspection.result} 이라 재고가 된 로트다 —"
                " 왜 돌려보내는지 사유를 적는다",
            )
        _must_be_a_reason_for_this_gate(session, request.nonconformity_code)
        # 합격 · 특채는 로트를 만든다 — 같은 트랜잭션에서 섰다(`incoming.receive`).
        lot = session.scalars(select(Lot).where(Lot.inspection_id == inspection.id)).one()
        if _lot_would_go_below_zero(session, lot, request.quantity):
            raise RefusedReturn(
                ReturnRefusal.MORE_THAN_THE_LOT_HOLDS,
                f"로트 {lot.lot_number} 에 남은 것보다 많이 돌려보내게 된다",
            )

    # **시각은 서버가 적는다.** 판정 시각과 같은 시계라 「판정보다 앞선 반품」이
    # 이 경로에서는 나지 않는다.
    returned_at = datetime.now()
    document = PurchaseReturn(
        inspection_id=inspection.id,
        inspection_result=inspection.result,
        lot_id=lot.id if lot is not None else None,
        settle_type=request.settle_type,
        nonconformity_code=request.nonconformity_code,
        quantity=request.quantity,
        returned_at=returned_at,
        returned_by=request.returned_by,
    )
    session.add(document)
    session.flush()

    if lot is None:
        return Returned(document.id, None)

    # **대물이든 대금이든 유형은 하나다** — 정산 구분은 문서에 한 번만 산다(원칙 ⑥).
    entry = StockLedgerEntry(
        lot_id=lot.id,
        txn_type=codes.TXN_PURCHASE_RETURN,
        quantity=request.quantity,
        occurred_at=returned_at,
        inspection_id=inspection.id,
        purchase_return_id=document.id,
    )
    session.add(entry)
    session.flush()
    return Returned(document.id, entry.id)
