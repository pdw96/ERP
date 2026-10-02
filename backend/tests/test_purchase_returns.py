"""구매반품이 원장에 닿는다 — 3단계 조각 1.

**원장이 처음으로 줄어든다.** 반품 문서가 무엇을 얼마나 왜 돌려보냈는지 적고, 재고가 된
로트였으면 원장에 구매반품출고 한 줄이 함께 선다. 불합격분은 재고가 된 적이 없으므로
원장 줄이 없다(원칙 ①).

**잔량은 트리거가 지킨다**(ADR 0013). 여러 줄의 합이라 CHECK 로 적을 수 없는 규칙이고,
그래서 이 파일의 절반은 데이터베이스가 **합을 보고** 거부하는지를 잰다. 마지막 절은 두
연결로 동시에 넣는다 — 한 연결 안의 순차 테스트는 잠금이 없어도 통과한다.
"""

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import codes
from app.db.base import Base
from app.db.code_attributes import (
    NonconformityAttribute,
    NonconformityStageRule,
    TxnTypeAttribute,
)
from app.db.inspection import Inspection
from app.db.inventory import Lot, PurchaseReturn, StockLedgerEntry
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

RECEIVED = date(2026, 9, 21)
JUDGED = datetime(2026, 9, 21, 9, 0)
RETURNED = datetime(2026, 9, 25, 14, 0)
REASON = "IQ-FM"
IN_KIND = "대물"
IN_MONEY = "대금"
# 총량 영향이 「감소」이지만 내는 쪽이 아직 없는 유형.
NOT_YET = "판매출고"


def _plant(session: Session) -> None:
    """합격한 로트 하나(500, 입고 줄까지)와 불합격한 입고분 하나(200)."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.WAREHOUSE, codes.WAREHOUSE_RAW, "원재료창고")
    add_code(session, codes.SETTLE_TYPE, IN_KIND, "대물정산")
    add_code(session, codes.SETTLE_TYPE, IN_MONEY, "대금정산")
    add_code(session, codes.NC_REASON, REASON, "이물")
    for txn_type in (*codes.LEDGER_TXN_TYPES, NOT_YET):
        add_code(session, codes.TXN_TYPE, txn_type)
    session.flush()

    session.add_all(
        [
            TxnTypeAttribute(
                code=codes.TXN_PURCHASE_RECEIPT,
                total_effect=codes.EFFECT_INCREASE,
                source_document_type="가입고",
            ),
            TxnTypeAttribute(
                code=codes.TXN_PURCHASE_RETURN,
                total_effect=codes.EFFECT_DECREASE,
                source_document_type="구매반품관리",
            ),
            TxnTypeAttribute(
                code=NOT_YET,
                total_effect=codes.EFFECT_DECREASE,
                source_document_type="출하 실적",
            ),
            NonconformityAttribute(code=REASON, measure_kind=codes.COUNTED_KIND),
        ]
    )
    session.flush()
    session.add(
        NonconformityStageRule(
            reason_code=REASON,
            stage_code=codes.STAGE_INCOMING,
            disposition="반품",
            special_acceptance_allowed=False,
        )
    )

    material = make_item(codes.RAW_MATERIAL, code="RM-01")
    supplier = make_partner(codes.SUPPLIER, code="SUP-01")
    session.add_all([material, supplier])
    session.flush()

    passed = _inspection(material, supplier, "SL-2026-0001", 500.0, codes.JUDGMENT_PASSED)
    failed = _inspection(material, supplier, "SL-2026-0002", 200.0, codes.JUDGMENT_FAILED)
    session.add_all([passed, failed])
    session.flush()

    lot = _lot(material, passed, "RM-01-260921-01")
    session.add(lot)
    session.flush()
    session.add(_receipt(lot))
    session.flush()


def _inspection(
    material: object, supplier: object, supplier_lot: str, quantity: float, result: str
) -> Inspection:
    return Inspection(
        item_id=material.id,  # type: ignore[attr-defined]
        item_type=material.item_type,  # type: ignore[attr-defined]
        material_group=material.material_group,  # type: ignore[attr-defined]
        supplier_id=supplier.id,  # type: ignore[attr-defined]
        supplier_type=supplier.partner_type,  # type: ignore[attr-defined]
        supplier_lot_number=supplier_lot,
        quantity=quantity,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=result,
        nonconformity_code=None if result == codes.JUDGMENT_PASSED else REASON,
    )


def _lot(material: object, inspection: Inspection, number: str) -> Lot:
    return Lot(
        item_id=material.id,  # type: ignore[attr-defined]
        item_type=material.item_type,  # type: ignore[attr-defined]
        lot_number=number,
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=inspection.quantity,
        received_date=RECEIVED,
        inspection_id=inspection.id,
        inspection_result=inspection.result,
    )


def _receipt(lot: Lot) -> StockLedgerEntry:
    return StockLedgerEntry(
        lot_id=lot.id,
        inspection_id=lot.inspection_id,
        txn_type=codes.TXN_PURCHASE_RECEIPT,
        quantity=lot.quantity,
        occurred_at=datetime(2026, 9, 21, 9, 30),
    )


@pytest.fixture
def prepared(session: Session) -> Session:
    _plant(session)
    return session


def _the_lot(session: Session) -> Lot:
    return session.query(Lot).one()


def _failed(session: Session) -> Inspection:
    return session.query(Inspection).filter_by(result=codes.JUDGMENT_FAILED).one()


def _lot_return(session: Session, quantity: float, **overrides: object) -> PurchaseReturn:
    """재고 로트를 돌려보내는 문서 하나. 넘긴 값만 달라진다."""
    lot = _the_lot(session)
    fields: dict[str, object] = {
        "inspection_id": lot.inspection_id,
        "inspection_result": lot.inspection_result,
        "lot_id": lot.id,
        "settle_type": IN_KIND,
        "nonconformity_code": REASON,
        "quantity": quantity,
        "returned_at": RETURNED,
        "returned_by": "자재 담당 1",
    }
    fields.update(overrides)
    return PurchaseReturn(**fields)


def _failed_return(session: Session, quantity: float, **overrides: object) -> PurchaseReturn:
    """불합격분을 돌려보내는 문서 하나 — 로트도 사유도 없다."""
    failed = _failed(session)
    fields: dict[str, object] = {
        "inspection_id": failed.id,
        "inspection_result": failed.result,
        "lot_id": None,
        "settle_type": IN_MONEY,
        "nonconformity_code": None,
        "quantity": quantity,
        "returned_at": RETURNED,
        "returned_by": "자재 담당 1",
    }
    fields.update(overrides)
    return PurchaseReturn(**fields)


def _return_line(document: PurchaseReturn, **overrides: object) -> StockLedgerEntry:
    """그 문서의 원장 줄 — 같은 로트 · 같은 수량 · 같은 시각."""
    fields: dict[str, object] = {
        "lot_id": document.lot_id,
        "inspection_id": document.inspection_id,
        "txn_type": codes.TXN_PURCHASE_RETURN,
        "quantity": document.quantity,
        "occurred_at": document.returned_at,
        "purchase_return_id": document.id,
    }
    fields.update(overrides)
    return StockLedgerEntry(**fields)


def _return_from_the_lot(session: Session, quantity: float) -> PurchaseReturn:
    """문서와 원장 줄을 함께 — 쓰기 경로가 한 트랜잭션에서 할 일."""
    document = _lot_return(session, quantity)
    session.add(document)
    session.flush()
    session.add(_return_line(document))
    session.flush()
    return document


def _balance(session: Session, lot_id: int) -> float:
    return float(
        session.execute(
            text(
                "SELECT coalesce(sum(CASE a.total_effect WHEN '증가' THEN e.quantity"
                " ELSE -e.quantity END), 0)"
                " FROM stock_ledger_entries AS e JOIN txn_type_attributes AS a"
                " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
                " WHERE e.lot_id = :lot"
            ),
            {"lot": lot_id},
        ).scalar_one()
    )


# ── 두 갈래 — 재고 로트 · 불합격분 ──────────────────────────────────────────


def test_a_lot_return_takes_its_quantity_out_of_the_ledger(prepared: Session) -> None:
    """**원장이 처음으로 줄어든다.** 문서 한 장과 원장 줄 한 줄이 함께 선다."""
    _return_from_the_lot(prepared, 200.0)

    assert _balance(prepared, _the_lot(prepared).id) == 300.0


def test_a_failed_delivery_goes_back_without_touching_the_ledger(prepared: Session) -> None:
    """**재고가 된 적 없는 것은 원장에서 빠질 것도 없다**(원칙 ①)."""
    lines_before = prepared.query(StockLedgerEntry).count()

    prepared.add(_failed_return(prepared, 200.0))
    prepared.flush()

    assert prepared.query(StockLedgerEntry).count() == lines_before


def test_a_passed_delivery_cannot_be_returned_without_its_lot(prepared: Session) -> None:
    """**합격한 것은 로트가 되었다** — 로트를 비우면 재고에서 빠지지 않는 반품이 선다."""
    prepared.add(_lot_return(prepared, 100.0, lot_id=None, nonconformity_code=None))
    with pytest.raises(IntegrityError, match="ck_purchase_return_lot_unless_failed"):
        prepared.flush()


def test_a_failed_delivery_cannot_name_a_lot(prepared: Session) -> None:
    """**불합격은 로트를 만들지 못했다** — 로트를 들면 없는 재고를 빼는 반품이 된다."""
    failed = _failed(prepared)
    prepared.add(
        _lot_return(prepared, 100.0, inspection_id=failed.id, inspection_result=failed.result)
    )
    with pytest.raises(IntegrityError, match="ck_purchase_return_lot_unless_failed"):
        prepared.flush()


def test_a_lot_return_names_the_judgement_that_made_the_lot(prepared: Session) -> None:
    """**그 로트를 만든 검사여야 한다.** 공급사는 검사에서 따라오므로, 남의 검사를 들면
    남의 공급사에게 반품한 기록이 선다."""
    made = prepared.get(Inspection, _the_lot(prepared).inspection_id)
    assert made is not None
    stranger = Inspection(
        item_id=made.item_id,
        item_type=made.item_type,
        material_group=made.material_group,
        supplier_id=made.supplier_id,
        supplier_type=made.supplier_type,
        supplier_lot_number="SL-2026-0003",
        quantity=500.0,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    prepared.add(stranger)
    prepared.flush()

    prepared.add(_lot_return(prepared, 100.0, inspection_id=stranger.id))
    with pytest.raises(IntegrityError, match="fk_purchase_return_lot"):
        prepared.flush()


# ── 문서의 칸 ───────────────────────────────────────────────────────────────


def test_a_lot_return_says_why(prepared: Session) -> None:
    """**재고가 된 것을 돌려보내는 이유는 이 문서에만 있다.**"""
    prepared.add(_lot_return(prepared, 100.0, nonconformity_code=None))
    with pytest.raises(IntegrityError, match="ck_purchase_return_reason_only_for_a_lot"):
        prepared.flush()


def test_a_failed_return_does_not_repeat_the_reason(prepared: Session) -> None:
    """**불합격의 사유는 그 검사가 이미 들고 있다** — 다시 적으면 같은 사실이 두 곳에 산다."""
    prepared.add(_failed_return(prepared, 100.0, nonconformity_code=REASON))
    with pytest.raises(IntegrityError, match="ck_purchase_return_reason_only_for_a_lot"):
        prepared.flush()


def test_the_settlement_is_a_settlement_code(prepared: Session) -> None:
    """정산 칸은 `SETTLE_TYPE` 의 코드만 받는다 — 있는 코드라도 다른 그룹이면 안 된다."""
    prepared.add(_failed_return(prepared, 100.0, settle_type=REASON))
    with pytest.raises(IntegrityError, match="fk_purchase_return_settle_type"):
        prepared.flush()


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_a_return_sends_back_something_countable(prepared: Session, bad: float) -> None:
    """**0 은 반품이 아니다** — 그리고 `NaN >= 0` 이 참이라 하한만으로는 막지 못한다."""
    prepared.add(_failed_return(prepared, bad))
    with pytest.raises(IntegrityError, match="ck_purchase_return_quantity"):
        prepared.flush()


@pytest.mark.parametrize("blank", ["", " ", "\t", "　"])
def test_a_return_says_who_sent_it(prepared: Session, blank: str) -> None:
    """낸 사람은 식별 칸 하나다 — **비어 보이는 값을 받지 않는다**(`is_present()`)."""
    prepared.add(_failed_return(prepared, 100.0, returned_by=blank))
    with pytest.raises(IntegrityError, match="ck_purchase_return_returned_by_is_present"):
        prepared.flush()


# ── 원장의 반품 줄 ──────────────────────────────────────────────────────────


def test_a_return_line_names_its_document(prepared: Session) -> None:
    """**근거 없는 반품 줄이 서지 않는다** — 문서가 비면 아래의 짝 대조가 통째로 빠진다."""
    lot = _the_lot(prepared)
    prepared.add(
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=codes.TXN_PURCHASE_RETURN,
            quantity=100.0,
            occurred_at=RETURNED,
        )
    )
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_return_names_its_document"):
        prepared.flush()


def test_a_receipt_line_does_not_carry_a_return_document(prepared: Session) -> None:
    """양방향이다 — 입고 줄이 반품의 근거를 들 수 없다."""
    document = _lot_return(prepared, 100.0)
    prepared.add(document)
    prepared.flush()

    lot = _the_lot(prepared)
    receipt = _receipt(lot)
    receipt.purchase_return_id = document.id
    prepared.add(receipt)
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_return_names_its_document"):
        prepared.flush()


@pytest.mark.parametrize(
    "drift",
    [{"quantity": 50.0}, {"occurred_at": datetime(2026, 9, 26, 9, 0)}],
    ids=["quantity", "time"],
)
def test_a_return_line_says_what_its_document_says(
    prepared: Session, drift: dict[str, object]
) -> None:
    """**문서는 100 을 돌려보냈는데 원장은 50 을 빼는 줄**이 서지 않는다 — 시각도 같다."""
    document = _lot_return(prepared, 100.0)
    prepared.add(document)
    prepared.flush()

    prepared.add(_return_line(document, **drift))
    with pytest.raises(IntegrityError, match="fk_stock_ledger_entry_purchase_return"):
        prepared.flush()


def test_one_document_takes_one_line(prepared: Session) -> None:
    """**한 번 돌려보낸 것을 두 번 빼지 않는다.**"""
    document = _return_from_the_lot(prepared, 100.0)

    prepared.add(_return_line(document))
    with pytest.raises(IntegrityError, match="uq_stock_ledger_entry_one_line_per_return"):
        prepared.flush()


def test_a_type_without_a_document_still_cannot_stand(prepared: Session) -> None:
    """**근거 문서가 선 유형만 받는다** — 판매출고는 속성 줄이 있어도 내는 쪽이 아직 없다."""
    lot = _the_lot(prepared)
    prepared.add(
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=NOT_YET,
            quantity=100.0,
            occurred_at=RETURNED,
        )
    )
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_txn_type_has_a_source"):
        prepared.flush()


# ── 잔량은 트리거가 지킨다 ──────────────────────────────────────────────────


def test_a_return_cannot_take_more_than_is_left(prepared: Session) -> None:
    """**있는 것보다 많이 뺄 수 없다** — 줄 하나가 아니라 합을 보는 규칙이다."""
    _return_from_the_lot(prepared, 300.0)

    document = _lot_return(prepared, 300.0, returned_at=datetime(2026, 9, 26, 9, 0))
    prepared.add(document)
    prepared.flush()
    prepared.add(_return_line(document))
    with pytest.raises(IntegrityError, match="잔량이 -100"):
        prepared.flush()


def test_returns_can_empty_a_lot_to_the_last_gram(prepared: Session) -> None:
    """**합은 `numeric` 으로 센다.** `double precision` 으로 더하면 500 − 0.1 − 0.3 − 499.6 이
    0 이 아니라 −5.7e-14 가 되고, 실제로 다 빠진 로트를 「음수」라며 거부한다.

    **수를 아무렇게나 고르면 이 검사는 아무것도 지키지 않는다.** 처음에는 33.3 · 66.7 · 400
    으로 쟀는데 그 합은 부동소수점에서도 공교롭게 0 보다 조금 **크게** 남아, 합을
    `double precision` 으로 세게 어긋내도 초록이었다(`docs/audit/mutations.md`). 지금의 수는
    부동소수점 합이 실제로 음수가 되는 것을 확인하고 골랐다.
    """
    for minute, quantity in enumerate((0.1, 0.3, 499.6)):
        document = _lot_return(prepared, quantity, returned_at=datetime(2026, 9, 26, 9, minute))
        prepared.add(document)
        prepared.flush()
        prepared.add(_return_line(document))
        prepared.flush()

    one_more = _lot_return(prepared, 0.1, returned_at=datetime(2026, 9, 26, 10, 0))
    prepared.add(one_more)
    prepared.flush()
    prepared.add(_return_line(one_more))
    with pytest.raises(IntegrityError, match="잔량이"):
        prepared.flush()


def test_a_receipt_carries_the_lots_quantity(prepared: Session) -> None:
    """**입고 줄은 로트 수량과 같다**(NC-70). 같은 수량이 로트와 원장에 나뉘어 들어가는데
    둘을 묶는 것이 쓰기 경로뿐이었다 — 그것은 제약이 아니라 우연이다."""
    lot = _the_lot(prepared)
    material = prepared.get(Inspection, lot.inspection_id)
    assert material is not None
    second = Inspection(
        item_id=material.item_id,
        item_type=material.item_type,
        material_group=material.material_group,
        supplier_id=material.supplier_id,
        supplier_type=material.supplier_type,
        supplier_lot_number="SL-2026-0004",
        quantity=300.0,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    prepared.add(second)
    prepared.flush()
    bare = Lot(
        item_id=lot.item_id,
        item_type=lot.item_type,
        lot_number="RM-01-260921-02",
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=300.0,
        received_date=RECEIVED,
        inspection_id=second.id,
        inspection_result=second.result,
    )
    prepared.add(bare)
    prepared.flush()

    receipt = _receipt(bare)
    receipt.quantity = 299.0
    prepared.add(receipt)
    with pytest.raises(IntegrityError, match="입고 줄의 수량"):
        prepared.flush()


def test_a_ledger_line_is_never_rewritten(prepared: Session) -> None:
    """**원칙 ⑦ — 취소는 반대 방향의 새 줄이다.** 고칠 수 있으면 잔량 규칙을 그 길로
    우회한다 — 입고 줄의 수량을 줄이면 이미 뺀 반품이 잔량을 음수로 만든다."""
    with pytest.raises(IntegrityError, match="고치거나 지우지 않는다"):
        prepared.execute(text("UPDATE stock_ledger_entries SET quantity = 1"))


def test_a_ledger_line_is_never_erased(prepared: Session) -> None:
    """지울 수 있으면 반품 줄만 남은 로트의 잔량이 음수가 된다."""
    with pytest.raises(IntegrityError, match="고치거나 지우지 않는다"):
        prepared.execute(text("DELETE FROM stock_ledger_entries"))


def test_a_lots_quantity_stays_once_the_ledger_has_spoken(prepared: Session) -> None:
    """**입고 줄과 로트 수량은 두 쪽에서 지켜야 한다** — 원장 쪽은 줄이 들어오는 순간만 본다."""
    lot = _the_lot(prepared)
    lot.quantity = 400.0
    with pytest.raises(IntegrityError, match="원장에 줄이 선 뒤에"):
        prepared.flush()


def test_a_lot_without_ledger_lines_can_still_be_corrected(prepared: Session) -> None:
    """**가드가 정상 경로를 막지 않는다** — 원장이 아직 말하지 않은 로트는 고칠 수 있다."""
    lot = _the_lot(prepared)
    second = Lot(
        item_id=lot.item_id,
        item_type=lot.item_type,
        lot_number="이월-0001",
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=10.0,
        received_date=RECEIVED,
    )
    prepared.add(second)
    prepared.flush()

    second.quantity = 12.0
    prepared.flush()

    assert prepared.get(Lot, second.id).quantity == 12.0  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("txn_type", "effect"),
    [
        (codes.TXN_PURCHASE_RETURN, codes.EFFECT_INCREASE),
        (codes.TXN_PURCHASE_RETURN, codes.EFFECT_BOTH),
    ],
)
def test_a_type_running_the_wrong_way_takes_no_line(
    prepared: Session, txn_type: str, effect: str
) -> None:
    """**거꾸로 선 유형은 첫 줄부터 받지 않는다**(Codex 리뷰 4 라운드). 방향을 고정하는
    트리거는 줄이 선 유형만 지키므로, 아직 줄이 없는 구매반품출고가 「증가」로 고쳐진 채면 첫
    반품이 잔량을 늘리고 그 줄이 곧바로 틀린 방향을 고정한다. 셀 줄 모르는 방향(양방향)도
    조용히 0 으로 세지 않는다. 구매입고는 심은 로트에 줄이 이미 있어 고정 트리거가 먼저
    막는다."""
    prepared.execute(
        text("UPDATE txn_type_attributes SET total_effect = :effect WHERE code = :code"),
        {"effect": effect, "code": txn_type},
    )
    document = _lot_return(prepared, 100.0)
    prepared.add(document)
    prepared.flush()
    prepared.add(_return_line(document))
    with pytest.raises(IntegrityError, match="원장은 이 유형을"):
        prepared.flush()


def _a_lot_without_its_receipt(session: Session) -> Lot:
    """같은 품목 · 공급사의 둘째 합격 로트 — **입고 줄을 아직 넣지 않았다.**"""
    first = _the_lot(session)
    passed = session.get(Inspection, first.inspection_id)
    assert passed is not None
    second = Inspection(
        item_id=passed.item_id,
        item_type=passed.item_type,
        material_group=passed.material_group,
        supplier_id=passed.supplier_id,
        supplier_type=passed.supplier_type,
        supplier_lot_number="SL-2026-0003",
        quantity=300.0,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
        nonconformity_code=None,
    )
    session.add(second)
    session.flush()
    lot = Lot(
        item_id=first.item_id,
        item_type=first.item_type,
        lot_number="RM-01-260921-02",
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=second.quantity,
        received_date=RECEIVED,
        inspection_id=second.id,
        inspection_result=second.result,
    )
    session.add(lot)
    session.flush()
    return lot


# ── 불합격분 — 원장 밖의 합 ─────────────────────────────────────────────────


def test_failed_returns_add_up_to_no_more_than_what_came(prepared: Session) -> None:
    """**원장 줄이 없는 반품도 합은 넘지 못한다.** 200 이 와서 떨어졌는데 250 을 돌려보낸
    기록이 서면 공급사와의 정산이 틀린다."""
    prepared.add(_failed_return(prepared, 150.0))
    prepared.flush()
    prepared.add(_failed_return(prepared, 50.0))
    prepared.flush()

    prepared.add(_failed_return(prepared, 0.5))
    with pytest.raises(IntegrityError, match="돌려보낸 합이"):
        prepared.flush()


def test_a_return_document_is_never_rewritten(prepared: Session) -> None:
    """**반품은 일어난 일이다** — 고칠 수 있으면 원장의 반품 줄과 갈린다."""
    prepared.add(_failed_return(prepared, 100.0))
    prepared.flush()

    with pytest.raises(IntegrityError, match="반품 문서는 고치거나 지우지 않는다"):
        prepared.execute(text("UPDATE purchase_returns SET quantity = 1"))


def test_a_return_document_is_never_erased(prepared: Session) -> None:
    """지울 수 있으면 공급사에게 간 물건이 장부에서 돌아온다."""
    prepared.add(_failed_return(prepared, 100.0))
    prepared.flush()

    with pytest.raises(IntegrityError, match="반품 문서는 고치거나 지우지 않는다"):
        prepared.execute(text("DELETE FROM purchase_returns"))


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


@contextmanager
def _committed_schema(engine: Engine, name: str) -> Iterator[Engine]:
    """커밋이 실제로 일어나는 스키마 하나 — 테스트 세션의 롤백 안에서는 잠금을 잴 수 없다."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={name}"}, poolclass=NullPool
    )
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            _plant(session)
            session.commit()
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _race(scoped: Engine, write: object) -> object:
    """**첫째가 잡은 채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를 커밋한다.**

    둘째가 기다리는지를 보지 않고 커밋하면, 둘째가 첫째의 커밋 **뒤에** 출발했을 때
    잠금이 없어도 통과한다 — 통과하면서 아무것도 지키지 않는 검사가 된다. 그래서
    둘째의 백엔드가 잠금을 기다리는 것(`pg_stat_activity`)을 확인하거나, 기다리지 않고
    끝나 버린 것을 확인한 뒤에 첫째를 놓는다. 잠금이 없으면 뒤쪽이 되고, 그때 둘째는
    통과해 테스트가 빨개진다.
    """
    first = Session(scoped)
    second = Session(scoped)
    outcome: dict[str, object] = {}
    try:
        write(first)  # type: ignore[operator]
        pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def go() -> None:
            try:
                write(second)  # type: ignore[operator]
                second.commit()
                outcome["second"] = "committed"
            except IntegrityError as error:
                second.rollback()
                outcome["second"] = error

        racer = threading.Thread(target=go)
        racer.start()
        deadline = time.monotonic() + 10
        with scoped.connect() as watcher:
            while racer.is_alive() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                ).scalar_one_or_none()
                if waiting == "Lock":
                    break
                time.sleep(0.02)
        first.commit()
        racer.join(10)
        assert not racer.is_alive(), "둘째가 끝나지 않았다"
    finally:
        first.close()
        second.close()
    return outcome["second"]


def test_two_returns_at_once_cannot_both_take_the_last_of_a_lot(engine: Engine) -> None:
    """**같은 잔량을 본 두 반품이 함께 통과하지 않는다.**

    잠그지 않으면 둘 다 「500 이 있다」를 보고 300 씩 뺀다 — 둘 다 커밋되면 잔량이
    −100 이다. 트리거가 로트 줄을 잠그므로 둘째는 첫째의 커밋을 기다리고, 그 뒤의 합은
    첫째의 줄을 본다.
    """
    with _committed_schema(engine, "return_race") as scoped:

        def take_three_hundred(session: Session) -> None:
            _return_from_the_lot(session, 300.0)

        second = _race(scoped, take_three_hundred)

        assert isinstance(second, IntegrityError), second
        assert "잔량이" in str(second)
        with Session(scoped) as session:
            assert _balance(session, _the_lot(session).id) == 200.0


def test_two_failed_returns_at_once_cannot_exceed_what_came(engine: Engine) -> None:
    """**원장 밖의 합도 같은 자리다** — 트리거가 그 검사 줄을 잠근다."""
    with _committed_schema(engine, "failed_return_race") as scoped:

        def send_back_one_fifty(session: Session) -> None:
            session.add(_failed_return(session, 150.0))
            session.flush()

        second = _race(scoped, send_back_one_fifty)

        assert isinstance(second, IntegrityError), second
        assert "돌려보낸 합이" in str(second)


# ── 리뷰가 낸 자리 — Codex 리뷰 · 감사 ㉟ ────────────────────────────────


def _immediately(session: Session) -> None:
    """커밋까지 미뤄 두는 검사를 지금 돌린다 — 테스트 세션은 커밋하지 않고 되돌리므로."""
    session.execute(text("SET CONSTRAINTS purchase_return_has_its_ledger_line IMMEDIATE"))


def test_a_lot_return_cannot_stand_without_its_ledger_line(prepared: Session) -> None:
    """**문서 → 원장 줄 방향**(NC-222 · Codex P1). 원장 쪽 제약은 줄 → 문서만 본다 — 문서가
    홀로 서면 공급사에게 간 물건이 잔량에서 빠지지 않는다."""
    prepared.add(_lot_return(prepared, 100.0))
    prepared.flush()

    with pytest.raises(IntegrityError, match="원장에 줄이 없다"):
        _immediately(prepared)


def test_a_lot_return_with_its_line_passes_the_commit_check(prepared: Session) -> None:
    """**가드가 정상 경로를 막지 않는다** — 문서를 먼저, 줄을 나중에 넣는 순서가 선다."""
    _return_from_the_lot(prepared, 100.0)

    _immediately(prepared)


def test_a_failed_return_needs_no_ledger_line(prepared: Session) -> None:
    """불합격분은 재고가 된 적이 없어 원장에 뺄 줄이 없다."""
    prepared.add(_failed_return(prepared, 100.0))
    prepared.flush()

    _immediately(prepared)


def test_a_types_direction_is_fixed_once_the_ledger_uses_it(prepared: Session) -> None:
    """**잔량의 부호가 사후에 뒤집히지 않는다**(NC-223 · Codex). 원장 줄이 선 유형의 방향을
    고치면 지나간 줄이 전부 거꾸로 다시 세어진다."""
    with pytest.raises(IntegrityError, match="원장에 줄이 선 뒤에 고치지 않는다"):
        prepared.execute(
            text("UPDATE txn_type_attributes SET total_effect = :effect WHERE code = :code"),
            {"effect": codes.EFFECT_DECREASE, "code": codes.TXN_PURCHASE_RECEIPT},
        )


@pytest.mark.parametrize(
    "change",
    [
        "quantity = 100",
        "judged_at = TIMESTAMP '2026-09-21 08:00'",
        "received_date = DATE '2026-09-20'",
        "supplier_id = (SELECT max(id) FROM partners)",
        "item_id = (SELECT max(id) FROM items)",
        "nonconformity_code = 'IQ-PKG'",
        "supplier_lot_number = 'SL-다른-배치'",
        "judged_by = '검사원 2'",
    ],
    ids=[
        "quantity",
        "judged_at",
        "received_date",
        "supplier",
        "item",
        "reason",
        "supplier_lot",
        "judged_by",
    ],
)
def test_a_returned_inspection_stays_as_it_was(prepared: Session, change: str) -> None:
    """**반품은 공급사 · 품목 · 수량 · 사유를 검사에서 따라간다**(NC-223 · Codex). 반품이 선 뒤
    검사가 움직이면 그 반품이 다른 공급사로 간 것이 되거나, 합 규칙의 분모가 바뀌거나, 지나간
    반품의 이유가 바뀐다(사유는 Codex 리뷰 2 라운드). 3 라운드가 공급사 로트번호를 더 냈을
    때 칸을 골라 고정하는 대신 줄을 통째로 고정했다 — 그래서 판정자처럼 아무도 짚지 않은
    칸도 여기서 잰다.

    값이 실제로 달라지도록 다른 공급사 · 품목을 하나씩 더 둔다 — 같은 값으로 고치면 트리거가
    「달라지지 않았다」로 넘겨 이 검사가 아무것도 묻지 않는다.
    """
    prepared.add_all([make_partner(codes.SUPPLIER, code="SUP-02"), make_item(code="RM-02")])
    add_code(prepared, codes.NC_REASON, "IQ-PKG", "포장")
    prepared.flush()
    prepared.add(NonconformityAttribute(code="IQ-PKG", measure_kind=codes.COUNTED_KIND))
    prepared.flush()
    prepared.add(
        NonconformityStageRule(
            reason_code="IQ-PKG",
            stage_code=codes.STAGE_INCOMING,
            disposition="반품",
            special_acceptance_allowed=False,
        )
    )
    prepared.flush()
    prepared.add(_failed_return(prepared, 100.0))
    prepared.flush()

    with pytest.raises(IntegrityError, match="반품이 가리킨다"):
        prepared.execute(text(f"UPDATE inspections SET {change} WHERE result = '불합격'"))


def test_an_inspection_nobody_returned_can_still_be_corrected(prepared: Session) -> None:
    """**가드가 정상 경로를 막지 않는다** — 반품도 로트도 가리키지 않는 검사는 고칠 수 있다."""
    prepared.execute(text("UPDATE inspections SET quantity = 180 WHERE result = '불합격'"))

    assert _failed(prepared).quantity == 180.0


def test_a_lot_carries_its_inspections_quantity(prepared: Session) -> None:
    """**검사 한 건은 로트 하나를 통째로 만든다**(NC-225). 같은 수량이 검사와 로트에 나뉘어
    살므로 쌍으로 묶는다 — 갈리면 「무엇이 들어왔나」가 표마다 다르게 읽힌다."""
    made = prepared.get(Inspection, _the_lot(prepared).inspection_id)
    assert made is not None
    second = Inspection(
        item_id=made.item_id,
        item_type=made.item_type,
        material_group=made.material_group,
        supplier_id=made.supplier_id,
        supplier_type=made.supplier_type,
        supplier_lot_number="SL-2026-0005",
        quantity=300.0,
        received_date=RECEIVED,
        judged_at=JUDGED,
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    prepared.add(second)
    prepared.flush()
    lot = _lot(made, second, "RM-01-260921-03")
    lot.item_id = made.item_id
    lot.quantity = 299.0
    prepared.add(lot)
    with pytest.raises(IntegrityError, match="fk_lot_inspection_quantity"):
        prepared.flush()


def test_an_inspection_that_made_a_lot_keeps_its_quantity(prepared: Session) -> None:
    """반대 방향 — 로트가 가리키는 동안 검사의 수량을 고치면 짝이 사라져 막힌다."""
    with pytest.raises(IntegrityError, match="fk_lot_inspection_quantity"):
        prepared.execute(text("UPDATE inspections SET quantity = 400 WHERE result = '합격'"))


def test_nothing_goes_back_before_it_was_judged(prepared: Session) -> None:
    """**판정받기 전의 물건은 돌려보낼 수 없다**(Codex). 시각이 앞선 반품은 잔량 합으로는
    통과하지만 지나간 시점의 잔량을 음수로 만든다."""
    prepared.add(_lot_return(prepared, 10.0, returned_at=datetime(2026, 9, 20, 9, 0)))
    with pytest.raises(IntegrityError, match="판정 시각"):
        prepared.flush()


def test_a_lot_return_uses_a_reason_the_incoming_stage_knows(prepared: Session) -> None:
    """**그 단계에서 쓸 수 있는 사유만**(Codex). 있는 코드라도 IQC 의 규칙이 없으면 받지
    않는다 — 사 온 자재를 완제품 접착력 불량으로 돌려보낸 기록이 서지 않는다."""
    add_code(prepared, codes.NC_REASON, "FQ-ADH", "접착력")
    prepared.flush()
    prepared.add(NonconformityAttribute(code="FQ-ADH", measure_kind=codes.COUNTED_KIND))
    prepared.flush()

    prepared.add(_lot_return(prepared, 10.0, nonconformity_code="FQ-ADH"))
    with pytest.raises(IntegrityError, match="fk_purchase_return_reason"):
        prepared.flush()


def test_two_returns_written_document_first_do_not_deadlock(engine: Engine) -> None:
    """**문서 먼저, 원장 줄 나중** — 쓰기 경로가 할 순서로 두 반품이 엇갈려도 끊기지 않는다
    (Codex · 감사 ㉟ OB-1).

    문서를 넣을 때 외래키 검사가 로트에 `KEY SHARE` 를 잡는다. 원장 트리거가 `FOR UPDATE`
    로 잠그면 둘이 서로의 `KEY SHARE` 를 기다려 교착으로 하나가 끊겼다. 첫째가 문서만 넣은
    채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째의 줄을 넣고 커밋한다.
    """
    with _committed_schema(engine, "return_interleave") as scoped:
        first = Session(scoped)
        second = Session(scoped)
        outcome: dict[str, object] = {}
        try:
            first_document = _lot_return(first, 10.0, returned_at=datetime(2026, 9, 25, 9, 0))
            first.add(first_document)
            first.flush()
            pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

            def go() -> None:
                try:
                    document = _lot_return(
                        second, 10.0, returned_at=datetime(2026, 9, 25, 10, 0)
                    )
                    second.add(document)
                    second.flush()
                    second.add(_return_line(document))
                    second.flush()
                    second.commit()
                    outcome["second"] = "committed"
                except DBAPIError as error:
                    second.rollback()
                    outcome["second"] = error

            racer = threading.Thread(target=go)
            racer.start()
            deadline = time.monotonic() + 10
            with scoped.connect() as watcher:
                while racer.is_alive() and time.monotonic() < deadline:
                    waiting = watcher.execute(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": pid},
                    ).scalar_one_or_none()
                    if waiting == "Lock":
                        break
                    time.sleep(0.02)
            first.add(_return_line(first_document))
            first.flush()
            first.commit()
            racer.join(10)
            assert not racer.is_alive(), "둘째가 끝나지 않았다"
        finally:
            first.close()
            second.close()

        assert outcome["second"] == "committed", outcome["second"]
        with Session(scoped) as session:
            assert _balance(session, _the_lot(session).id) == 480.0


# ── Codex 리뷰 2 라운드 ──────────────────────────────────────────────────


def test_nothing_goes_back_before_it_came_in(prepared: Session) -> None:
    """**입고 줄의 시각과도 견준다.** 판정(09:00) 뒤 입고(09:30) 전인 09:15 의 반품은 들어오기
    전의 물건이다 — 판정 시각만 보면 통과하고, 잔량 합은 시각을 보지 않아 뒤의 입고를 먹는다."""
    prepared.add(_lot_return(prepared, 10.0, returned_at=datetime(2026, 9, 21, 9, 15)))
    with pytest.raises(IntegrityError, match="입고 시각"):
        prepared.flush()


def test_the_balance_is_looked_up_by_lot(prepared: Session) -> None:
    """**잔량을 셀 길이 있다.** 트리거가 줄마다 그 로트의 줄을 합하는데 `lot_id` 로 찾을
    인덱스가 입고 줄만 담은 부분 인덱스뿐이면, 줄이 늘수록 넣을 때마다 표를 훑으며 로트 잠금을
    쥔다.
    작은 표에서는 계획기가 인덱스를 고르지 않으므로 인덱스가 있다는 것을 직접 본다."""
    indexes = {
        name
        for (name,) in prepared.execute(
            text(
                "SELECT indexname FROM pg_indexes"
                " WHERE tablename = 'stock_ledger_entries' AND indexdef NOT LIKE '%WHERE%'"
                " AND indexdef LIKE '%(lot_id)'"
            )
        )
    }
    assert indexes == {"ix_stock_ledger_entry_lot"}, indexes


def test_a_direction_change_waits_for_the_first_line_of_its_type(engine: Engine) -> None:
    """**첫 줄과 방향 변경이 엇갈려도 고정이 비켜 가지 않는다**(Codex 리뷰 2 라운드).

    그 유형의 첫 줄이 커밋되기 전에 방향을 바꾸면, 고정 트리거는 「줄이 없다」를 보고 통과시키고
    원장 트리거는 옛 방향으로 셌다 — 둘 다 커밋되면 잔량이 거꾸로 읽힌다. 원장 트리거가 유형
    속성 줄을 `FOR SHARE` 로 읽어 그 갱신을 첫 줄의 커밋 뒤로 세운다.
    """
    with _committed_schema(engine, "effect_race") as scoped:
        first = Session(scoped)
        second = Session(scoped)
        outcome: dict[str, object] = {}
        try:
            _return_from_the_lot(first, 10.0)
            pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

            def go() -> None:
                try:
                    second.execute(
                        text(
                            "UPDATE txn_type_attributes SET total_effect = :effect"
                            " WHERE code = :code"
                        ),
                        {"effect": codes.EFFECT_INCREASE, "code": codes.TXN_PURCHASE_RETURN},
                    )
                    second.commit()
                    outcome["second"] = "committed"
                except IntegrityError as error:
                    second.rollback()
                    outcome["second"] = error

            racer = threading.Thread(target=go)
            racer.start()
            deadline = time.monotonic() + 10
            with scoped.connect() as watcher:
                while racer.is_alive() and time.monotonic() < deadline:
                    waiting = watcher.execute(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": pid},
                    ).scalar_one_or_none()
                    if waiting == "Lock":
                        break
                    time.sleep(0.02)
            first.commit()
            racer.join(10)
            assert not racer.is_alive(), "둘째가 끝나지 않았다"
        finally:
            first.close()
            second.close()

        assert isinstance(outcome["second"], IntegrityError), outcome["second"]
        with Session(scoped) as session:
            assert _balance(session, _the_lot(session).id) == 490.0


def test_failed_returns_are_looked_up_by_inspection(prepared: Session) -> None:
    """**불합격분의 합을 셀 길이 있다**(Codex 리뷰 3 라운드). 트리거가 검사 줄을 잠근 채 같은
    검사의 반품을 합하는데 `inspection_id` 로 찾을 인덱스가 없으면, 반품이 쌓일수록 표를 훑으며
    잠금을 쥔다."""
    indexes = {
        name
        for (name,) in prepared.execute(
            text(
                "SELECT indexname FROM pg_indexes"
                " WHERE tablename = 'purchase_returns' AND indexdef LIKE '%(inspection_id)'"
            )
        )
    }
    assert indexes == {"ix_purchase_return_inspection"}, indexes


# ── Codex 리뷰 4 라운드 ──────────────────────────────────────────────────


def test_a_receipt_written_later_does_not_launder_an_earlier_return(prepared: Session) -> None:
    """**시각은 원장 줄이 들어올 때도 견준다.** 입고 줄이 아직 없는 로트에 반품 문서(09-25)를
    먼저 넣으면 문서 쪽은 견줄 입고 시각이 없어 지나간다. 같은 트랜잭션에서 입고 줄(09-26)을
    넣고 반품 줄을 마지막에 넣으면 합은 음수가 아니고 지연 트리거도 줄을 본다 — 들어오기 전에
    나간 물건이 남는다."""
    lot = _a_lot_without_its_receipt(prepared)
    document = PurchaseReturn(
        inspection_id=lot.inspection_id,
        inspection_result=lot.inspection_result,
        lot_id=lot.id,
        settle_type=IN_KIND,
        nonconformity_code=REASON,
        quantity=50.0,
        returned_at=RETURNED,
        returned_by="자재 담당 1",
    )
    prepared.add(document)
    prepared.flush()
    late = _receipt(lot)
    late.occurred_at = datetime(2026, 9, 26, 9, 0)
    prepared.add(late)
    prepared.flush()

    prepared.add(_return_line(document))
    with pytest.raises(IntegrityError, match="입고 시각"):
        prepared.flush()
