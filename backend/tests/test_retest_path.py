"""재검사 쓰기 경로 — 3단계 조각 4. **만료된 로트가 다시 검사받는다.**

조각 3 이 표와 트리거를 세웠고, 이 조각은 그것을 **한 트랜잭션으로 부르는 자리**다. 여기서
검사하는 것은 —

- **합격이면 새 만료일이 판정일에서 설정기간을 센 값인가**(ADR 0017), 불합격이면 잔량 전부가
  폐기 한 줄로 나가는가
- **트리거가 막는 것을 쓰기 경로가 먼저 이름으로 막는가** — 그리고 **같은 경계로** 막는가
- **두 재검사가 동시에 와도 둘째가 이름을 받는가** — 쓰기 경로가 트리거와 같은 순서로 잠그지
  않으면 둘째는 묻는 순간의 상태를 보고 통과해 트리거의 500 을 맞는다

트리거 자체는 `tests/test_retest.py` 가 본다.
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import codes
from app.db.base import Base
from app.db.code_attributes import (
    NonconformityAttribute,
    NonconformityStageRule,
    TxnTypeAttribute,
)
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item, Partner
from app.services import incoming
from app.services.incoming import Measurement, RefusedInspection
from app.services.retests import IncomingRetest, Retested, RetestRefusal, retest
from app.services.returns import RefusedReturn, ReturnRefusal, return_to_supplier
from tests.factories import add_code, make_item
from tests.test_return_path import _from_the_lot, _retire, plant_return_codes
from tests.test_write_path import (
    _FOREIGN_REASON,
    _GRAIN,
    _MOISTURE,
    _MOISTURE_REASON,
    GROUP,
    _standard,
    plant_master_data,
)

SHELF_LIFE = 365
_PACKAGE, _PACKAGE_REASON = "포장", "IQ-PKG"
# 규격 안의 수분 — 수분은 상한 0.5 하나다.
FINE = 0.3


def plant_retest_data(session: Session) -> None:
    """관문 1 의 기준정보 위에 재검사가 기대는 것 — 시드와 같은 모양.

    수분은 경시변화이고 입도는 아니다. 세는 경시변화 항목(포장)과 그 사유가 하나 선다. 재검사
    사유 규칙은 수분 · 포장이고, 이물의 사유(`IQ-DOC`)도 재검사에 열어 둔다 — 「재검사가 보지
    않는 항목의 사유」를 잴 자리다.
    """
    plant_master_data(session)
    plant_return_codes(session)
    add_code(session, codes.INSP_STAGE, codes.RETEST_STAGE, "재검사")
    add_code(session, codes.INSP_ITEM, _PACKAGE)
    add_code(session, codes.NC_REASON, _PACKAGE_REASON, "포장 불량")
    add_code(session, codes.TXN_TYPE, codes.TXN_DISPOSAL)
    session.flush()
    session.add(
        TxnTypeAttribute(
            code=codes.TXN_DISPOSAL,
            total_effect=codes.EFFECT_DECREASE,
            source_document_type="재검사 불합격",
        )
    )
    _standard(
        session,
        _PACKAGE,
        upper_spec_limit=None,
        lower_spec_limit=None,
        center_line=None,
        unit=None,
        time_variant=True,
    )
    session.flush()
    session.execute(
        text(
            "UPDATE process_inspection_standards SET time_variant = TRUE WHERE item_code = :c"
        ),
        {"c": _MOISTURE},
    )
    session.add(
        NonconformityAttribute(
            code=_PACKAGE_REASON,
            measure_kind=codes.COUNTED_KIND,
            inspection_item_code=_PACKAGE,
        )
    )
    session.flush()
    session.add_all(
        NonconformityStageRule(
            reason_code=reason,
            stage_code=codes.RETEST_STAGE,
            disposition="폐기",
            special_acceptance_allowed=False,
        )
        for reason in (_MOISTURE_REASON, _PACKAGE_REASON, _FOREIGN_REASON)
    )
    session.execute(text("UPDATE items SET shelf_life_days = :days"), {"days": SHELF_LIFE})
    session.flush()


def an_expired_lot(
    session: Session,
    *,
    expires: date | None = None,
    quantity: float = 500.0,
    number: str = "RM-01-250101-01",
    receipt: bool = True,
) -> Lot:
    """IQC 를 지나 오래 전에 들어온 로트 — 넘긴 만료일로, 입고 줄은 넘기면 뺀다.

    **관문 1 의 쓰기 경로로 짓지 않는다** — 그 경로는 이미 지난 자재를 합격으로 세우지 않는다
    (`material_is_already_expired`). 로트의 만료일은 고칠 수도 없으므로 처음부터 지난 날로
    짓는다.
    """
    today = date.today()
    arrived = today - timedelta(days=400)
    material = session.scalars(select(Item).where(Item.code == "RM-01")).one()
    supplier = session.scalars(select(Partner).where(Partner.code == "SUP-01")).one()
    passed = Inspection(
        item_id=material.id,
        item_type=material.item_type,
        material_group=material.material_group,
        supplier_id=supplier.id,
        supplier_type=supplier.partner_type,
        supplier_lot_number=f"SL-{number}",
        quantity=quantity,
        received_date=arrived,
        judged_at=datetime.combine(arrived, datetime.min.time()),
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    session.add(passed)
    session.flush()
    lot = Lot(
        item_id=material.id,
        item_type=material.item_type,
        lot_number=number,
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        stock_type=codes.STOCK_GOOD,
        quantity=quantity,
        received_date=arrived,
        passed_date=arrived,
        expiry_date=today - timedelta(days=10) if expires is None else expires,
        inspection_id=passed.id,
        inspection_result=passed.result,
    )
    session.add(lot)
    session.flush()
    if receipt:
        session.add(
            StockLedgerEntry(
                lot_id=lot.id,
                inspection_id=passed.id,
                txn_type=codes.TXN_PURCHASE_RECEIPT,
                quantity=quantity,
                occurred_at=datetime.combine(arrived, datetime.min.time()),
            )
        )
        session.flush()
    return lot


@pytest.fixture
def planted(session: Session) -> Session:
    plant_retest_data(session)
    return session


def a_retest(lot_id: int, moisture: float = FINE, **overrides: object) -> IncomingRetest:
    """수분 하나를 다시 잰 재검사 — 규격(≤ 0.5) 밖이면 불합격이다."""
    fields: dict[str, object] = {
        "lot_id": lot_id,
        "judged_by": "검사원 1",
        "measurements": (Measurement(_MOISTURE, moisture),),
    }
    fields.update(overrides)
    return IncomingRetest(**fields)  # type: ignore[arg-type]


def _refused(session: Session, request: IncomingRetest) -> str:
    with pytest.raises(RefusedInspection) as refused:
        retest(session, request)
    # **나가는 이름은 이 경로의 열거에 있다** — 검사의 함수가 던진 이름도.
    assert refused.value.code in {name.value for name in RetestRefusal}, refused.value.code
    return refused.value.code


def _balance(session: Session, lot_id: int) -> float:
    return float(
        session.execute(
            text(
                "SELECT coalesce(sum(CASE a.total_effect WHEN '증가' THEN e.quantity::numeric"
                " ELSE -e.quantity::numeric END), 0)"
                " FROM stock_ledger_entries AS e JOIN txn_type_attributes AS a"
                " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
                " WHERE e.lot_id = :lot"
            ),
            {"lot": lot_id},
        ).scalar_one()
    )


# ── 두 갈래 — 합격 · 불합격 ─────────────────────────────────────────────────


def test_a_pass_renews_the_expiry_from_the_day_it_was_judged(planted: Session) -> None:
    """**새 만료일은 판정일 + 설정기간이다**(ADR 0017) — 로트의 옛 만료일은 그대로다."""
    lot = an_expired_lot(planted)
    labelled = lot.expiry_date

    retested = retest(planted, a_retest(lot.id))

    assert retested == Retested(
        retested.inspection_id,
        codes.JUDGMENT_PASSED,
        None,
        date.today() + timedelta(days=SHELF_LIFE),
        None,
    )
    planted.expire_all()
    assert planted.get(Lot, lot.id).expiry_date == labelled  # type: ignore[union-attr]
    assert _balance(planted, lot.id) == 500.0


def test_a_retest_pins_what_it_measured_as_a_time_variant_retest(planted: Session) -> None:
    """측정 줄은 재검사의 단계와 경시변화 플래그를 들고 그때의 규격을 박는다."""
    retested = retest(planted, a_retest(an_expired_lot(planted).id))

    row = planted.scalars(
        select(InspectionMeasurement).where(
            InspectionMeasurement.inspection_id == retested.inspection_id
        )
    ).one()
    assert (row.item_code, row.inspection_stage, row.standard_time_variant) == (
        _MOISTURE,
        codes.RETEST_STAGE,
        True,
    )
    assert row.applied_upper_spec == 0.5


def test_a_failure_throws_away_everything_left(planted: Session) -> None:
    """**불합격이면 잔량 전부가 폐기 한 줄로 나간다** — 앞서 돌려보낸 것을 뺀 나머지다."""
    lot = an_expired_lot(planted)
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 120.0))  # type: ignore[arg-type]

    retested = retest(planted, a_retest(lot.id, moisture=0.9))

    assert (retested.result, retested.nonconformity_code, retested.renewed_expiry_date) == (
        codes.JUDGMENT_FAILED,
        _MOISTURE_REASON,
        None,
    )
    entry = planted.get(StockLedgerEntry, retested.ledger_entry_id)
    assert entry is not None
    assert (entry.txn_type, entry.quantity, entry.retest_id) == (
        codes.TXN_DISPOSAL,
        380.0,
        retested.inspection_id,
    )
    assert _balance(planted, lot.id) == 0.0


def test_a_failure_whose_balance_does_not_add_up_in_binary_still_empties_the_lot(
    planted: Session,
) -> None:
    """**잔량은 트리거와 같은 자릿수로 센다** — `double` 로 빼면 100 − 33.3 − 66.6 이 0.1 이
    되지 않아, 그 수로 낸 폐기 줄을 트리거가 「잔량이 음수가 된다」로 거절한다."""
    lot = an_expired_lot(planted, quantity=100.0)
    # `double` 로 세면 남는 것이 0.1 이 아니라 0.10000000000000853 이다.
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 33.3))  # type: ignore[arg-type]
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 66.6))  # type: ignore[arg-type]

    retest(planted, a_retest(lot.id, moisture=0.9))

    assert _balance(planted, lot.id) == pytest.approx(0.0, abs=0)


def test_a_counted_failure_a_person_saw_fails_the_lot(planted: Session) -> None:
    """**계산이 보지 못하는 것은 사람이 적는다** — 세는 경시변화 항목(포장)의 결함이다."""
    retested = retest(
        planted, a_retest(an_expired_lot(planted).id, nonconformity_code=_PACKAGE_REASON)
    )

    assert (retested.result, retested.nonconformity_code) == (
        codes.JUDGMENT_FAILED,
        _PACKAGE_REASON,
    )


def test_a_retired_reason_a_person_wrote_is_named(planted: Session) -> None:
    """**꺼진 사유 코드는 새 판정에서 고르지 못한다**(이슈 #73) — 재검사 단계의 규칙 줄이 남아
    있어도 그렇다. 검사와 같은 함수가 같은 이름으로 막는다."""
    lot = an_expired_lot(planted)
    _retire(planted, codes.NC_REASON, _PACKAGE_REASON)

    assert _refused(planted, a_retest(lot.id, nonconformity_code=_PACKAGE_REASON)) == (
        RetestRefusal.REASON_IS_NOT_ACTIVE
    )


def test_a_failure_stands_even_when_the_item_has_no_shelf_life(planted: Session) -> None:
    """불합격은 새 만료일이 필요 없다 — 설정기간이 없어도 받는다."""
    planted.execute(text("UPDATE items SET shelf_life_days = NULL"))

    retested = retest(planted, a_retest(an_expired_lot(planted).id, moisture=0.9))

    assert retested.result == codes.JUDGMENT_FAILED


# ── 이름으로 막는다 ─────────────────────────────────────────────────────────


def test_an_unknown_lot_is_named(planted: Session) -> None:
    assert _refused(planted, a_retest(999_999)) == RetestRefusal.UNKNOWN_LOT


def test_a_pass_without_a_shelf_life_is_named(planted: Session) -> None:
    """**새 만료일을 지어내지 않는다**(ADR 0017) — 품목이 그 뒤에 무기한으로 바뀐 경우다."""
    lot = an_expired_lot(planted)
    planted.execute(text("UPDATE items SET shelf_life_days = NULL"))

    assert _refused(planted, a_retest(lot.id)) == RetestRefusal.ITEM_HAS_NO_SHELF_LIFE


def test_a_lot_that_expires_today_is_still_in_date(planted: Session) -> None:
    """**만료일 당일까지는 쓸 수 있다** — 트리거와 같은 경계다(아래 「경계」 절이 둘을
    견준다)."""
    lot = an_expired_lot(planted, expires=date.today())

    assert _refused(planted, a_retest(lot.id)) == RetestRefusal.LOT_HAS_NOT_EXPIRED


def test_a_lot_without_an_expiry_is_named(planted: Session) -> None:
    lot = an_expired_lot(planted)
    forever = Lot(
        item_id=lot.item_id,
        item_type=lot.item_type,
        lot_number="RM-01-OPENING-01",
        lot_origin=codes.LOT_FROM_SUPPLIER,
        warehouse=codes.WAREHOUSE_RAW,
        quantity=10.0,
        received_date=lot.received_date,
    )
    planted.add(forever)
    planted.flush()

    assert _refused(planted, a_retest(forever.id)) == RetestRefusal.LOT_HAS_NO_EXPIRY


def test_a_lot_with_nothing_left_is_named(planted: Session) -> None:
    lot = an_expired_lot(planted, receipt=False)

    assert _refused(planted, a_retest(lot.id)) == RetestRefusal.NOTHING_LEFT_IN_THE_LOT


def test_a_lot_that_failed_is_not_retested_again(planted: Session) -> None:
    lot = an_expired_lot(planted)
    retest(planted, a_retest(lot.id, moisture=0.9))

    assert _refused(planted, a_retest(lot.id)) == RetestRefusal.LOT_ALREADY_FAILED_A_RETEST


def test_a_renewed_lot_is_in_date_again(planted: Session) -> None:
    """**지금 만료일은 가장 최근에 합격한 재검사의 것이다.**"""
    lot = an_expired_lot(planted)
    retest(planted, a_retest(lot.id))

    assert _refused(planted, a_retest(lot.id)) == RetestRefusal.LOT_HAS_NOT_EXPIRED


def test_a_lot_that_is_not_raw_material_is_named(planted: Session) -> None:
    """재검사도 원자재만이다 — 검사 표가 원자재만 받는다. 막지 않으면 외래키 · CHECK 의 500
    이다."""
    add_code(planted, codes.WAREHOUSE, codes.WAREHOUSE_FINISHED, "제품창고")
    add_code(planted, codes.PROCESS, "적층경화")
    product = make_item(codes.FINISHED_GOODS, code="FG-01", process="적층경화")
    planted.add(product)
    planted.flush()
    made = Lot(
        item_id=product.id,
        item_type=product.item_type,
        lot_number="FG-01-250101-01",
        lot_origin=codes.LOT_FROM_OWN,
        warehouse=codes.WAREHOUSE_FINISHED,
        quantity=10.0,
        produced_date=date.today() - timedelta(days=400),
        expiry_date=date.today() - timedelta(days=10),
    )
    planted.add(made)
    planted.flush()

    assert _refused(planted, a_retest(made.id)) == RetestRefusal.LOT_IS_NOT_RAW_MATERIAL


def test_nothing_to_measure_again_is_named(planted: Session) -> None:
    """**재지 않는 재검사는 통과다** — 그 합격이 만료일을 늘린다."""
    lot = an_expired_lot(planted)
    planted.execute(
        text(
            "UPDATE process_inspection_standards SET time_variant = FALSE WHERE item_code = :c"
        ),
        {"c": _MOISTURE},
    )

    assert (
        _refused(planted, a_retest(lot.id, measurements=()))
        == RetestRefusal.NOTHING_TO_RETEST_FOR_MATERIAL_GROUP
    )


@pytest.mark.parametrize(
    ("measurements", "expected"),
    [
        (
            (Measurement(_MOISTURE, FINE), Measurement(_MOISTURE, FINE)),
            RetestRefusal.ITEM_MEASURED_TWICE,
        ),
        (
            (Measurement(_MOISTURE, FINE), Measurement(_GRAIN, 30.0)),
            RetestRefusal.ITEM_IS_NOT_RETESTED,
        ),
        (
            (Measurement(_MOISTURE, FINE), Measurement(_PACKAGE, 1.0)),
            RetestRefusal.ITEM_IS_NOT_MEASURED,
        ),
        ((), RetestRefusal.MEASUREMENT_IS_MISSING),
    ],
    ids=["twice", "not-time-variant", "counted", "missing"],
)
def test_measurements_that_do_not_fit_the_retest_are_named(
    planted: Session, measurements: tuple[Measurement, ...], expected: RetestRefusal
) -> None:
    """**재검사는 시간이 바꾸는 재는 항목을 빠짐없이 한 번씩 잰다** — 측정 줄의 외래키가 막기
    전에 이름으로."""
    lot = an_expired_lot(planted)

    assert _refused(planted, a_retest(lot.id, measurements=measurements)) == expected


@pytest.mark.parametrize(
    ("moisture", "reason", "expected"),
    [
        (0.9, _PACKAGE_REASON, RetestRefusal.REASON_COMES_WITH_A_COMPUTED_DEVIATION),
        (FINE, "IQ-PSD", RetestRefusal.REASON_IS_NOT_USABLE_AT_THIS_GATE),
        (FINE, _MOISTURE_REASON, RetestRefusal.REASON_IS_NOT_A_COUNTED_ONE),
        (FINE, _FOREIGN_REASON, RetestRefusal.REASON_IS_NOT_INSPECTED_FOR_THIS_MATERIAL),
    ],
    ids=["with-a-deviation", "not-at-retest", "measured-reason", "not-time-variant"],
)
def test_a_reason_a_person_wrote_is_named_when_it_does_not_fit(
    planted: Session, moisture: float, reason: str, expected: RetestRefusal
) -> None:
    """**사람이 적는 사유는 재검사 단계에서 쓸 수 있고, 재검사가 보는 세는 항목의 것뿐이다.**
    이물(`IQ-DOC`)은 재검사에 열려 있어도 이물이 경시변화가 아니라 재검사가 보지 않는다."""
    lot = an_expired_lot(planted)

    assert (
        _refused(planted, a_retest(lot.id, moisture=moisture, nonconformity_code=reason))
        == expected
    )


@pytest.mark.parametrize(
    ("item_code", "expected"),
    [
        (None, RetestRefusal.REASON_IS_DERIVED_BY_THE_SYSTEM),
        (_MOISTURE, RetestRefusal.REASON_POINTS_AT_A_MEASURED_ITEM),
    ],
    ids=["no-item", "measured-item"],
)
def test_a_counted_reason_a_person_cannot_see_is_named(
    planted: Session, item_code: str | None, expected: RetestRefusal
) -> None:
    """세는 사유라도 사람이 보는 항목이 없거나(시스템이 다는 사유), 그 항목을 재검사가
    **잰다면** 사람이 적지 못한다 — 검사와 같은 함수가 같은 이름으로 막는다."""
    add_code(planted, codes.NC_REASON, "RT-X", "시험")
    planted.flush()
    planted.add(
        NonconformityAttribute(
            code="RT-X", measure_kind=codes.COUNTED_KIND, inspection_item_code=item_code
        )
    )
    planted.flush()
    planted.add(
        NonconformityStageRule(
            reason_code="RT-X",
            stage_code=codes.RETEST_STAGE,
            disposition="폐기",
            special_acceptance_allowed=False,
        )
    )
    planted.flush()
    lot = an_expired_lot(planted)

    assert _refused(planted, a_retest(lot.id, nonconformity_code="RT-X")) == expected


def test_a_deviation_with_no_reason_at_retest_is_named(planted: Session) -> None:
    """이탈을 적을 사유가 그 단계에 없으면 지어내지 않는다."""
    lot = an_expired_lot(planted)
    planted.execute(
        text(
            "DELETE FROM nonconformity_stage_rules WHERE stage_code = '재검사'"
            " AND reason_code = :code"
        ),
        {"code": _MOISTURE_REASON},
    )

    assert (
        _refused(planted, a_retest(lot.id, moisture=0.9))
        == RetestRefusal.NO_REASON_FOR_THE_DEVIATION
    )


def test_the_names_shared_with_the_inspection_path_mean_the_same() -> None:
    """**검사와 겹치는 이름은 같은 값이다**(ADR 0014) — 재검사가 부르는 검사의 함수가 던지는
    이름이 이 경로의 열거에 없으면 스펙이 실제로 나가는 이름을 들지 못한다."""
    shared = {
        incoming.Refusal.NO_REASON_FOR_THE_DEVIATION,
        incoming.Refusal.REASON_IS_NOT_USABLE_AT_THIS_GATE,
        incoming.Refusal.REASON_IS_NOT_A_COUNTED_ONE,
        incoming.Refusal.REASON_IS_DERIVED_BY_THE_SYSTEM,
        incoming.Refusal.REASON_IS_NOT_INSPECTED_FOR_THIS_MATERIAL,
        incoming.Refusal.REASON_POINTS_AT_A_MEASURED_ITEM,
        incoming.Refusal.REASON_IS_NOT_ACTIVE,
    }

    assert {name.value for name in shared} <= {name.value for name in RetestRefusal}


def test_the_return_path_names_a_retest_it_cannot_take(planted: Session) -> None:
    """**반품은 수입검사만 가리킨다** — 재검사의 id 는 있는 검사라 `unknown_inspection` 으로
    말하면 부르는 쪽이 id 를 의심한다(감사 ㊴). 반품 경로의 이름이지만 재검사가 서야 날 수
    있어 여기 둔다."""
    lot = an_expired_lot(planted)
    retested = retest(planted, a_retest(lot.id))

    with pytest.raises(RefusedReturn) as refused:
        return_to_supplier(planted, _from_the_lot(retested.inspection_id, 1.0))

    assert refused.value.code == ReturnRefusal.INSPECTION_IS_NOT_INCOMING


# ── 경계 — 쓰기 경로와 트리거가 같은 날을 가른다 (ADR 0016) ───────────────


@pytest.mark.parametrize(
    ("days_past", "takes_a_retest"),
    [(0, False), (1, True)],
    ids=["expires-today", "expired-yesterday"],
)
def test_the_write_path_and_the_trigger_draw_the_same_line(
    planted: Session, days_past: int, takes_a_retest: bool
) -> None:
    """**둘이 갈리면 트리거가 이긴다 — 이름 없는 500 이다.** 같은 로트를 쓰기 경로와 SQL 로 한
    번씩 넣어 본다. 오늘 만료면 둘 다 거절하고, 어제 만료면 둘 다 받는다."""
    lot = an_expired_lot(planted, expires=date.today() - timedelta(days=days_past))

    attempt = planted.begin_nested()
    if takes_a_retest:
        retest(planted, a_retest(lot.id))
    else:
        assert _refused(planted, a_retest(lot.id)) == RetestRefusal.LOT_HAS_NOT_EXPIRED
    attempt.rollback()

    material = planted.get(Item, lot.item_id)
    assert material is not None
    by_hand = Inspection(
        inspection_stage=codes.RETEST_STAGE,
        item_id=material.id,
        item_type=material.item_type,
        material_group=GROUP,
        target_lot_id=lot.id,
        judged_at=datetime.now(),
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
        renewed_expiry_date=date.today() + timedelta(days=SHELF_LIFE),
    )
    if takes_a_retest:
        planted.add(by_hand)
        planted.flush()
    else:
        with pytest.raises(IntegrityError, match="만료되지 않은 로트"):
            planted.add(by_hand)
            planted.flush()


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


@contextmanager
def _committed_schema(engine: Engine, name: str) -> Iterator[tuple[Engine, int]]:
    """커밋이 실제로 일어나는 스키마와 그 안의 만료된 로트 하나."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={name}"}, poolclass=NullPool
    )
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            plant_retest_data(session)
            lot_id = an_expired_lot(session).id
            session.commit()
        yield scoped, lot_id
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _race(scoped: Engine, write: Callable[[Session], None]) -> object:
    """첫째가 잡은 채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를 커밋한다 —
    `tests/test_return_path.py` 의 같은 이름 함수와 같은 자리다."""
    first = Session(scoped)
    second = Session(scoped)
    outcome: dict[str, object] = {}
    try:
        write(first)
        pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def go() -> None:
            try:
                write(second)
                second.commit()
                outcome["second"] = "committed"
            except (RefusedInspection, IntegrityError) as error:
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


@pytest.mark.parametrize(
    ("moisture", "expected"),
    [
        (FINE, RetestRefusal.LOT_HAS_NOT_EXPIRED),
        (0.9, RetestRefusal.LOT_ALREADY_FAILED_A_RETEST),
    ],
    ids=["behind-a-pass", "behind-a-failure"],
)
def test_two_retests_at_once_the_second_is_named(
    engine: Engine, moisture: float, expected: RetestRefusal
) -> None:
    """**둘째는 이름을 받는다** — 트리거의 500 이 아니라. 쓰기 경로가 트리거와 같은 로트 줄을
    먼저 잠그므로, 둘째는 첫째의 커밋 뒤의 상태를 보고 묻는다."""
    with _committed_schema(engine, f"retest_path_race_{expected.value[:20]}") as (
        scoped,
        lot_id,
    ):

        def judge(session: Session) -> None:
            retest(session, a_retest(lot_id, moisture))

        second = _race(scoped, judge)

        assert isinstance(second, RefusedInspection), second
        assert second.code == expected
