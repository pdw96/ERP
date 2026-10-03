"""만료 재검사 — 만료된 로트 하나를 다시 본다(3단계).

**재검사는 로트를 만들지 않고 있는 로트를 가리킨다.** 유효기간이 지난 로트가 재고를 떠나지
않고 검사로 돌아와, **경시변화 항목만** 다시 잰다. 합격하면 새 만료일이 이 재검사에 박히고
(로트의 옛 만료일은 고치지 않는다 — 라벨에 찍혀 나간 값이다), 불합격하면 그 로트의 잔량
전부가 원장에 폐기출고 한 줄로 나간다.

### 계산이 먼저이고 사람이 나중이다 (원칙 ③)

IQC 와 같다 — 검사원이 넣는 것은 측정값과, 계산이 보지 못하는 세는 항목의 결함뿐이다. 판정은
계산이 내고, **새 만료일도 계산이 낸다** — 판정일에서 그 품목의 설정기간을 센다(ADR 0017).
특채는 없다 — 관문 2 가 범위 밖이다.

### 트리거가 막는 것을 먼저 이름으로 막는다 (ADR 0016)

「만료된 로트만 재검사를 받는다」는 데이터베이스의 트리거
(`retest_comes_only_to_an_expired_lot`)가 강제한다. 여기서 같은 것을 먼저 묻는 것은 **거절에
이름을 주려는 것**이고, 그래서 **트리거와 같은 순서로 잠그고 같은 경계로 견준다** — 로트 줄을
`FOR NO KEY UPDATE` 로 잡은 뒤 묻는다. 잠그지 않고 물으면 같은 로트에 동시에 온 둘째는 묻는
순간의 상태를 보고 통과해 트리거의 500 을 맞는다. 둘이 갈리면 트리거가 이긴다(이름 없는
거절이 난다) — 경계가 같은지는 테스트가 문다.

### 한 트랜잭션이다

재검사 · 측정값 · 폐기 줄이 한 번에 들어가거나 아무것도 들어가지 않는다. 떨어진 재검사가 폐기 줄
없이 서는 것은 커밋할 때 트리거가 막는다(`retest_failure_has_its_disposal_line`).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import TxnTypeAttribute
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item
from app.db.quality import ProcessInspectionStandard
from app.services.incoming import (
    Measurement,
    RefusedInspection,
    allows_special_acceptance,
    measures,
    must_be_a_reason_a_person_inspects,
    reason_for,
    within_spec,
)


class RetestRefusal(StrEnum):
    """재검사를 거절할 때 `detail[].type` 으로 나가는 이름 — **목록이 여기 한 벌이다.**

    경로마다 열거를 둔다(ADR 0014). **검사와 겹치는 이름은 같은 값이다** — 측정값과 사유를 보는
    규칙은 같은 함수(`app/services/incoming.py`)가 보고, 그 함수는 검사의 `Refusal` 을
    던진다. 그 값이 이 열거에도 있어야 스펙이 실제로 나가는 이름을 든다 —
    `tests/test_retest_path.py` 가 견준다.
    """

    UNKNOWN_LOT = "unknown_lot"
    LOT_IS_NOT_RAW_MATERIAL = "lot_is_not_raw_material"
    LOT_ALREADY_FAILED_A_RETEST = "lot_already_failed_a_retest"
    LOT_HAS_NO_EXPIRY = "lot_has_no_expiry"
    LOT_HAS_NOT_EXPIRED = "lot_has_not_expired"
    NOTHING_LEFT_IN_THE_LOT = "nothing_left_in_the_lot"
    NOTHING_TO_RETEST_FOR_MATERIAL_GROUP = "nothing_to_retest_for_material_group"
    ITEM_MEASURED_TWICE = "item_measured_twice"
    ITEM_IS_NOT_RETESTED = "item_is_not_retested"
    ITEM_IS_NOT_MEASURED = "item_is_not_measured"
    MEASUREMENT_IS_MISSING = "measurement_is_missing"
    NO_REASON_FOR_THE_DEVIATION = "no_reason_for_the_deviation"
    REASON_COMES_WITH_A_COMPUTED_DEVIATION = "reason_comes_with_a_computed_deviation"
    REASON_IS_NOT_USABLE_AT_THIS_GATE = "reason_is_not_usable_at_this_gate"
    REASON_IS_NOT_A_COUNTED_ONE = "reason_is_not_a_counted_one"
    REASON_IS_DERIVED_BY_THE_SYSTEM = "reason_is_derived_by_the_system"
    REASON_IS_NOT_INSPECTED_FOR_THIS_MATERIAL = "reason_is_not_inspected_for_this_material"
    REASON_POINTS_AT_A_MEASURED_ITEM = "reason_points_at_a_measured_item"
    ITEM_HAS_NO_SHELF_LIFE = "item_has_no_shelf_life"
    REASON_IS_NOT_ACTIVE = "reason_is_not_active"


@dataclass(frozen=True)
class IncomingRetest:
    """받은 재검사 한 건 — 어느 로트를 · 누가 · 무엇을 쟀나."""

    lot_id: int
    judged_by: str
    measurements: tuple[Measurement, ...]
    # 세는 경시변화 항목(포장)에서 사람이 잡은 결함. 계산은 이것을 보지 못한다.
    nonconformity_code: str | None = None


@dataclass(frozen=True)
class Retested:
    """재검사가 끝난 뒤 남은 것."""

    inspection_id: int
    result: str
    nonconformity_code: str | None
    renewed_expiry_date: date | None
    ledger_entry_id: int | None


def _refuse(code: RetestRefusal, message: str) -> RefusedInspection:
    return RefusedInspection(code, message)


def _lot(session: Session, lot_id: int) -> Lot:
    """**로트 줄을 잠근다** — 트리거가 맨 먼저 잡는 줄이다.

    `key_share=True` 가 `FOR NO KEY UPDATE` 다 — 트리거와 같은 잠금이고, 재검사 줄을 넣을 때
    외래키가 잡는 `KEY SHARE` 와 부딪치지 않는다(`app/db/ledger_guards.py` 머리).
    """
    lot = session.scalars(
        select(Lot).where(Lot.id == lot_id).with_for_update(key_share=True)
    ).one_or_none()
    if lot is None:
        raise _refuse(RetestRefusal.UNKNOWN_LOT, f"그런 로트가 없다: {lot_id}")
    return lot


def _balance(session: Session, lot: Lot) -> float:
    """그 로트의 원장 합 — 트리거와 같은 셈이다. 로트 줄은 `_lot()` 이 이미 잠갔다."""
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
    total = session.scalar(
        select(func.coalesce(func.sum(signed), 0))
        .join(
            TxnTypeAttribute,
            (TxnTypeAttribute.group_code == StockLedgerEntry.txn_type_group)
            & (TxnTypeAttribute.code == StockLedgerEntry.txn_type),
        )
        .where(StockLedgerEntry.lot_id == lot.id)
    )
    return float(total or 0)


def _must_have_expired(session: Session, lot: Lot, today: date) -> None:
    """**만료된 로트만 받는다** — 트리거와 같은 셋을 같은 순서로 묻는다.

    앞선 불합격 → 지금 만료일(가장 최근에 합격한 재검사의 것, 없으면 로트의 것) → 경계. 경계는
    **만료일 당일까지는 쓸 수 있다** — 지금 만료일이 오늘보다 앞설 때만 만료다.
    """
    retests = select(Inspection).where(Inspection.target_lot_id == lot.id)
    if session.scalars(retests.where(Inspection.result == codes.JUDGMENT_FAILED)).first():
        raise _refuse(
            RetestRefusal.LOT_ALREADY_FAILED_A_RETEST,
            f"로트 {lot.lot_number} 는 이미 재검사에서 떨어져 폐기됐다",
        )
    latest = session.scalars(
        retests.where(Inspection.result == codes.JUDGMENT_PASSED).order_by(
            Inspection.judged_at.desc(), Inspection.id.desc()
        )
    ).first()
    expires = latest.renewed_expiry_date if latest is not None else lot.expiry_date
    if expires is None:
        raise _refuse(
            RetestRefusal.LOT_HAS_NO_EXPIRY,
            f"로트 {lot.lot_number} 는 만료일이 없다 — 재검사는 만료된 로트의 일이다",
        )
    if expires >= today:
        raise _refuse(
            RetestRefusal.LOT_HAS_NOT_EXPIRED,
            f"로트 {lot.lot_number} 의 지금 만료일({expires})이 오늘({today})보다 앞서지 않는다"
            " — 만료일 당일까지는 쓸 수 있다",
        )


def _time_variant_standards(
    session: Session, material_group: str
) -> dict[str, ProcessInspectionStandard]:
    """그 무리의 수입 기준 가운데 **시간이 바꾸는 것** — 재검사가 다시 보는 것은 이것뿐이다."""
    rows = session.scalars(
        select(ProcessInspectionStandard).where(
            ProcessInspectionStandard.process_code.in_(codes.MATERIAL_GROUPED_PROCESSES),
            ProcessInspectionStandard.material_group == material_group,
            ProcessInspectionStandard.time_variant.is_(True),
        )
    ).all()
    return {row.item_code: row for row in rows}


def _measured(
    request: IncomingRetest, standards: dict[str, ProcessInspectionStandard]
) -> dict[str, float]:
    """측정값을 기준에 맞춘다 — 관문 1 과 같은 넷을 재검사의 기준으로 묻는다."""
    counted = Counter(measurement.item_code for measurement in request.measurements)
    twice = sorted(code for code, times in counted.items() if times > 1)
    if twice:
        raise _refuse(
            RetestRefusal.ITEM_MEASURED_TWICE,
            f"같은 항목을 두 번 쟀다: {', '.join(twice)}",
        )
    measured = {m.item_code: m.value for m in request.measurements}
    unknown = sorted(set(measured) - set(standards))
    if unknown:
        # **경시변화가 아닌 항목은 다시 보지 않는다** — 시간이 바꾸지 않는 값은 IQC 의 판정이
        # 그대로다. 받아 두면 재검사 측정 줄의 외래키가 문다.
        raise _refuse(
            RetestRefusal.ITEM_IS_NOT_RETESTED,
            f"재검사가 다시 보는 항목이 아니다: {', '.join(unknown)} —"
            " 재검사는 시간이 바꾸는 항목만 잰다",
        )
    counted_items = sorted(code for code in measured if not measures(standards[code]))
    if counted_items:
        raise _refuse(
            RetestRefusal.ITEM_IS_NOT_MEASURED,
            f"세는 항목에는 잰 값을 적을 수 없다: {', '.join(counted_items)} —"
            " 그 항목의 결함은 사유로 적는다",
        )
    missing = sorted(
        code
        for code, standard in standards.items()
        if measures(standard) and code not in measured
    )
    if missing:
        raise _refuse(
            RetestRefusal.MEASUREMENT_IS_MISSING,
            f"다시 재야 하는 항목의 측정값이 없다: {', '.join(missing)}",
        )
    return measured


def retest(session: Session, request: IncomingRetest) -> Retested:
    """재검사 한 건을 받아 판정하고, 합격이면 새 만료일을 박고 불합격이면 잔량 전부를 버린다.

    **부르는 쪽이 트랜잭션을 연다.** `receive()` 와 같이 `flush` 까지만 한다.
    """
    lot = _lot(session, request.lot_id)
    item = session.get(Item, lot.item_id)
    assert item is not None  # 로트는 품목을 가리킨다 (외래키)
    if item.material_group is None:
        # 재검사도 원자재만이다 — 검사 표가 원자재만 받는다
        # (`ck_inspection_item_is_raw_material`).
        raise _refuse(
            RetestRefusal.LOT_IS_NOT_RAW_MATERIAL,
            f"재검사가 보는 것은 원자재 로트뿐이다 — {lot.lot_number} 는 {item.item_type} 이다",
        )

    judged_at = datetime.now()
    _must_have_expired(session, lot, judged_at.date())
    left = _balance(session, lot)
    if left <= 0:
        raise _refuse(
            RetestRefusal.NOTHING_LEFT_IN_THE_LOT,
            f"로트 {lot.lot_number} 에 남은 것이 없다 — 없는 물건은 재검사하지 않는다",
        )

    standards = _time_variant_standards(session, item.material_group)
    if not any(measures(standard) for standard in standards.values()):
        # **재지 않는 재검사는 검사가 아니라 통과다** — 그 합격이 만료일을 늘린다. 관문 1 의
        # `nothing_to_measure_for_material_group` 과 같은 자리다.
        raise _refuse(
            RetestRefusal.NOTHING_TO_RETEST_FOR_MATERIAL_GROUP,
            f"{item.material_group} 의 수입 기준에 시간이 바꾸는 재는 항목이 한 줄도 없다 —"
            " 무엇을 다시 보고 만료일을 늘리는지 측정값 줄이 말하지 못한다",
        )
    measured = _measured(request, standards)

    out_of_spec = sorted(
        code for code, value in measured.items() if not within_spec(value, standards[code])
    )
    reason: str | None = None
    if out_of_spec:
        if request.nonconformity_code is not None:
            raise _refuse(
                RetestRefusal.REASON_COMES_WITH_A_COMPUTED_DEVIATION,
                f"계산이 이미 이탈을 잡았다({', '.join(out_of_spec)}) —"
                f" 사유 칸은 하나라 {request.nonconformity_code} 를 함께 적을 수 없다",
            )
        reason = reason_for(session, out_of_spec[0], codes.RETEST_STAGE)
    elif request.nonconformity_code is not None:
        allows_special_acceptance(session, request.nonconformity_code, codes.RETEST_STAGE)
        must_be_a_reason_a_person_inspects(
            session, request.nonconformity_code, standards, scope="재검사 항목"
        )
        reason = request.nonconformity_code

    result = codes.JUDGMENT_PASSED if reason is None else codes.JUDGMENT_FAILED
    renewed: date | None = None
    if result == codes.JUDGMENT_PASSED:
        if item.shelf_life_days is None:
            # **새 만료일을 지어내지 않는다**(ADR 0017). 로트에는 만료일이 있었는데 품목이 그
            # 뒤에 무기한으로 바뀐 경우다 — 설정기간을 정한 사람이 없으면 셀 것이 없다.
            raise _refuse(
                RetestRefusal.ITEM_HAS_NO_SHELF_LIFE,
                f"{item.code} 에 설정기간이 없다 —"
                " 판정일에서 셀 것이 없어 새 만료일을 낼 수 없다",
            )
        renewed = judged_at.date() + timedelta(days=item.shelf_life_days)

    inspection = Inspection(
        inspection_stage=codes.RETEST_STAGE,
        item_id=item.id,
        item_type=item.item_type,
        material_group=item.material_group,
        target_lot_id=lot.id,
        judged_at=judged_at,
        judged_by=request.judged_by,
        result=result,
        nonconformity_code=reason,
        renewed_expiry_date=renewed,
    )
    session.add(inspection)
    session.flush()

    for code, value in sorted(measured.items()):
        standard = standards[code]
        session.add(
            InspectionMeasurement(
                inspection_id=inspection.id,
                item_code=code,
                process_code=standard.process_code,
                material_group=item.material_group,
                inspection_stage=codes.RETEST_STAGE,
                standard_time_variant=True,
                measured_value=value,
                applied_upper_spec=standard.upper_spec_limit,
                applied_lower_spec=standard.lower_spec_limit,
                applied_unit=standard.unit,
            )
        )

    if result == codes.JUDGMENT_PASSED:
        session.flush()
        return Retested(inspection.id, result, None, renewed, None)

    # ── 떨어진 로트는 잔량 전부가 나간다 ───────────────────────────────────
    # 잔량이 있는 로트는 입고 줄이 있고, 입고 줄은 로트를 만든 검사와 쌍이다.
    assert lot.inspection_id is not None
    entry = StockLedgerEntry(
        lot_id=lot.id,
        inspection_id=lot.inspection_id,
        txn_type=codes.TXN_DISPOSAL,
        quantity=left,
        occurred_at=judged_at,
        retest_id=inspection.id,
        retest_result=result,
    )
    session.add(entry)
    session.flush()
    return Retested(inspection.id, result, reason, None, entry.id)
