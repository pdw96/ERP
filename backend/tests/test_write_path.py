"""쓰기 경로 — 조각 11. **합격이 로트를 만든다.**

표 넷이 선 뒤 이 조각이 하는 일은 **그 표들을 한 트랜잭션으로 묶는 것**이다.
그래서 여기서 검사하는 것은 칸이 아니라 —

- **판정이 계산되는가** (원칙 ③ — 사람이 넣는 것은 측정값뿐)
- **불합격이 로트를 만들지 못하는가** (원칙 ①)
- **로트와 원장 줄이 함께 들어가거나 함께 없는가** (성공기준 ③)
- **같은 품목·같은 날에 둘이 동시에 들어와도 번호가 겹치지 않는가** (감사 W-2)
"""

from datetime import date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core import codes, locks
from app.db.code_attributes import NonconformityAttribute, NonconformityStageRule
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item
from app.db.quality import ProcessInspectionStandard
from app.services.incoming import (
    IncomingInspection,
    Measurement,
    RefusedInspection,
    _next_lot_number,
    receive,
)
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

GROUP = "분체"
RECEIVED = date(2026, 9, 21)

# 시드와 같은 모양 — 재는 항목 둘과 세는 항목 하나.
_GRAIN, _MOISTURE, _FOREIGN = "입도", "수분", "이물"
# 특채가 열린 사유와 닫힌 사유를 하나씩 세운다 — 어느 코드가 열려 있는지는
# 시드가 정하고, 여기서는 그 갈림만 흉내 낸다.
_GRAIN_REASON, _MOISTURE_REASON, _FOREIGN_REASON = "IQ-PSD", "IQ-MOI", "IQ-DOC"


def _standard(session: Session, item_code: str, **overrides: object) -> None:
    fields: dict[str, object] = {
        "process_code": "수입",
        "process_group": codes.PROCESS,
        "item_code": item_code,
        "item_group": codes.INSP_ITEM,
        "material_group": GROUP,
        "material_group_group": codes.MATERIAL_GROUP,
        "upper_spec_limit": 50.0,
        "lower_spec_limit": 10.0,
        "center_line": 30.0,
        "warning_ratio": codes.DEFAULT_WARNING_RATIO,
        "sigma_source": codes.SIGMA_UNDECIDED,
        "unit": "µm",
    }
    fields.update(overrides)
    session.add(ProcessInspectionStandard(**fields))


def _reason(
    session: Session,
    code: str,
    *,
    item_code: str | None,
    measure_kind: str,
    special: bool,
) -> None:
    add_code(session, codes.NC_REASON, code, code)
    session.flush()
    session.add(
        NonconformityAttribute(
            code=code, measure_kind=measure_kind, inspection_item_code=item_code
        )
    )
    session.flush()
    session.add(
        NonconformityStageRule(
            reason_code=code,
            stage_code=codes.STAGE_INCOMING,
            disposition="반품",
            special_acceptance_allowed=special,
        )
    )
    session.flush()


@pytest.fixture
def prepared(session: Session) -> Session:
    """시드와 같은 모양의 최소 기준정보 — 분체 하나가 항목 셋을 받는다."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.WAREHOUSE, codes.WAREHOUSE_RAW, "원재료창고")
    add_code(session, codes.TXN_TYPE, codes.TXN_PURCHASE_RECEIPT)
    for item_code in (_GRAIN, _MOISTURE, _FOREIGN):
        add_code(session, codes.INSP_ITEM, item_code)
    session.flush()

    from app.db.code_attributes import TxnTypeAttribute

    session.add(
        TxnTypeAttribute(
            code=codes.TXN_PURCHASE_RECEIPT,
            total_effect=codes.EFFECT_INCREASE,
            source_document_type="가입고",
        )
    )

    _standard(session, _GRAIN)
    _standard(session, _MOISTURE, upper_spec_limit=0.5, lower_spec_limit=None, center_line=0.2)
    # **세는 항목** — 규격이 없으므로 측정 줄이 서지 않는다.
    _standard(
        session,
        _FOREIGN,
        upper_spec_limit=None,
        lower_spec_limit=None,
        center_line=None,
        unit=None,
    )

    _reason(
        session,
        _GRAIN_REASON,
        item_code=_GRAIN,
        measure_kind=codes.MEASURED_KIND,
        special=False,
    )
    _reason(
        session,
        _MOISTURE_REASON,
        item_code=_MOISTURE,
        measure_kind=codes.MEASURED_KIND,
        special=True,
    )
    _reason(
        session,
        _FOREIGN_REASON,
        item_code=_FOREIGN,
        measure_kind=codes.COUNTED_KIND,
        special=True,
    )

    session.add_all(
        [
            make_item(codes.RAW_MATERIAL, code="RM-01", material_group=GROUP),
            make_partner(codes.SUPPLIER, code="SUP-01"),
        ]
    )
    session.flush()
    return session


def _request(**overrides: object) -> IncomingInspection:
    """규격 안에 드는 측정값을 들고 오는 검사 하나."""
    fields: dict[str, object] = {
        "item_code": "RM-01",
        "supplier_code": "SUP-01",
        "supplier_lot_number": "SL-2026-0001",
        "quantity": 500.0,
        "judged_by": "검사원 1",
        "received_date": RECEIVED,
        "measurements": (Measurement(_GRAIN, 30.0), Measurement(_MOISTURE, 0.3)),
    }
    fields.update(overrides)
    return IncomingInspection(**fields)  # type: ignore[arg-type]


# ── 합격이 로트를 만든다 ────────────────────────────────────────────────────


def test_a_pass_makes_a_lot_and_one_ledger_line(prepared: Session) -> None:
    """**원칙 ① 이 실제로 도는 자리다.** 판정이 로트를 만들고 원장에 한 줄이 남는다."""
    judged = receive(prepared, _request())

    assert judged.result == codes.JUDGMENT_PASSED
    assert judged.nonconformity_code is None

    lot = prepared.query(Lot).one()
    entry = prepared.query(StockLedgerEntry).one()
    assert lot.id == judged.lot_id
    assert entry.lot_id == lot.id
    assert entry.txn_type == codes.TXN_PURCHASE_RECEIPT
    # **로트가 자기를 만든 검사를 가리킨다** — 특채 표식이 사는 곳도 여기다.
    assert lot.inspection_id == judged.inspection_id
    assert lot.inspection_result == codes.JUDGMENT_PASSED


def test_the_lot_number_is_ours_and_the_supplier_number_stays_on_the_inspection(
    prepared: Session,
) -> None:
    """**남이 지은 번호를 우리 유일키에 쓰지 않는다.**

    두 공급사가 같은 번호를 써도 부딪치지 않는 이유가 이것이다. 공급사가 붙여
    온 번호는 검사 쪽에 그대로 남아 되짚을 수 있다.
    """
    receive(prepared, _request())

    lot = prepared.query(Lot).one()
    inspection = prepared.query(Inspection).one()
    assert lot.lot_number == "RM-01-260921-01"
    assert inspection.supplier_lot_number == "SL-2026-0001"


def test_a_second_receipt_of_the_same_item_that_day_gets_the_next_serial(
    prepared: Session,
) -> None:
    """그날 그 품목의 마지막 번호에서 이어 받는다."""
    receive(prepared, _request())
    receive(prepared, _request(supplier_lot_number="SL-2026-0002"))

    assert sorted(lot.lot_number for lot in prepared.query(Lot)) == [
        "RM-01-260921-01",
        "RM-01-260921-02",
    ]


def test_the_measurements_pin_the_spec_they_were_judged_against(prepared: Session) -> None:
    """**세는 항목은 측정 줄이 서지 않는다** — 잰 값이 없기 때문이다."""
    receive(prepared, _request())

    rows = {row.item_code: row for row in prepared.query(InspectionMeasurement)}
    assert set(rows) == {_GRAIN, _MOISTURE}
    assert (rows[_GRAIN].applied_lower_spec, rows[_GRAIN].applied_upper_spec) == (10.0, 50.0)
    # 한쪽만 있는 규격도 그대로 박힌다.
    assert rows[_MOISTURE].applied_lower_spec is None


def test_the_expiry_is_pinned_from_the_shelf_life(prepared: Session) -> None:
    """**파생해 저장하는 예외 하나** — 라벨에 찍혀 나가므로 설정기간을 고쳐도 안 바뀐다."""
    item = prepared.query(Item).filter_by(code="RM-01").one()
    item.shelf_life_days = 365
    prepared.flush()

    receive(prepared, _request())
    pinned = prepared.query(Lot).one().expiry_date

    item.shelf_life_days = 30
    prepared.flush()
    assert prepared.query(Lot).one().expiry_date == pinned


def test_a_material_without_a_shelf_life_gets_no_expiry(prepared: Session) -> None:
    """설정기간이 없는 자재(시트 · 필름)는 **비어서 선다** — 지어내지 않는다."""
    item = prepared.query(Item).filter_by(code="RM-01").one()
    item.shelf_life_days = None
    prepared.flush()

    receive(prepared, _request())

    assert prepared.query(Lot).one().expiry_date is None


# ── 불합격은 재고가 되지 않는다 ────────────────────────────────────────────


def test_a_measurement_outside_the_spec_makes_no_lot(prepared: Session) -> None:
    """**원칙 ①.** 판정이 불합격이면 로트도 원장 줄도 서지 않는다.

    그리고 사유는 **지어내지 않는다** — 사유 코드가 이미 검사 항목을 가리키고
    있으므로 그 방향을 뒤집어 끌어온다.
    """
    judged = receive(
        prepared,
        _request(measurements=(Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3))),
    )

    assert judged.result == codes.JUDGMENT_FAILED
    assert judged.nonconformity_code == _GRAIN_REASON
    assert judged.lot_id is None and judged.ledger_entry_id is None
    assert prepared.query(Lot).count() == 0
    assert prepared.query(StockLedgerEntry).count() == 0
    # **측정값은 남는다** — 일어난 일은 지우지 않는다. 왜 떨어졌는지가 거기 있다.
    assert prepared.query(InspectionMeasurement).count() == 2


def test_a_failed_judgement_can_never_be_attached_to_a_lot(prepared: Session) -> None:
    """**쓰기 경로가 막는 것과 데이터베이스가 막는 것은 다른 겹이다.**

    경로를 우회해 직접 로트를 만들어도 외래키와 CHECK 가 되받는다 — 성공기준 ①
    의 「주석이 아니라 제약으로」가 여기서 확인된다.
    """
    judged = receive(
        prepared,
        _request(measurements=(Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3))),
    )
    item = prepared.query(Item).filter_by(code="RM-01").one()

    prepared.add(
        Lot(
            item_id=item.id,
            item_type=item.item_type,
            lot_number="손으로-만든-로트",
            lot_origin=codes.LOT_FROM_SUPPLIER,
            warehouse=codes.WAREHOUSE_RAW,
            stock_type=codes.STOCK_GOOD,
            quantity=1.0,
            received_date=RECEIVED,
            inspection_id=judged.inspection_id,
            inspection_result=codes.JUDGMENT_FAILED,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_one_judgement_makes_at_most_one_lot(prepared: Session) -> None:
    """판정은 검사 한 건에 하나다 — 둘이 서면 같은 합격으로 재고가 두 벌 생긴다."""
    judged = receive(prepared, _request())
    item = prepared.query(Item).filter_by(code="RM-01").one()

    prepared.add(
        Lot(
            item_id=item.id,
            item_type=item.item_type,
            lot_number="RM-01-260921-99",
            lot_origin=codes.LOT_FROM_SUPPLIER,
            warehouse=codes.WAREHOUSE_RAW,
            stock_type=codes.STOCK_GOOD,
            quantity=1.0,
            received_date=RECEIVED,
            inspection_id=judged.inspection_id,
            inspection_result=codes.JUDGMENT_PASSED,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 특채는 사람만 낼 수 있다 ───────────────────────────────────────────────


def test_a_special_acceptance_makes_a_lot_that_points_at_its_inspection(
    prepared: Session,
) -> None:
    """**원칙 ① 의 예외 하나.** 로트가 생기되 표식은 검사 쪽에 있다."""
    judged = receive(
        prepared,
        _request(
            measurements=(Measurement(_GRAIN, 30.0), Measurement(_MOISTURE, 9.9)),
            special_acceptance=True,
        ),
    )

    assert judged.result == codes.JUDGMENT_SPECIAL
    assert judged.nonconformity_code == _MOISTURE_REASON
    lot = prepared.query(Lot).one()
    assert lot.inspection_result == codes.JUDGMENT_SPECIAL
    # 로트에 「특채」 칸이 없다 — 표식은 가리키는 검사가 든다.
    assert not hasattr(lot, "special_acceptance")


def test_a_special_acceptance_on_a_closed_reason_is_refused(prepared: Session) -> None:
    """특채가 열려 있지 않은 사유로는 낼 수 없다 — **이름으로 말하고 돌려보낸다.**"""
    with pytest.raises(RefusedInspection, match=_GRAIN_REASON):
        receive(
            prepared,
            _request(
                measurements=(Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3)),
                special_acceptance=True,
            ),
        )


def test_a_special_acceptance_on_a_passing_inspection_is_refused(prepared: Session) -> None:
    """합격인데 특채는 말이 되지 않는다 — 특채는 **불합격을 뒤집는** 결정이다."""
    with pytest.raises(RefusedInspection, match="합격"):
        receive(prepared, _request(special_acceptance=True))


def test_a_person_may_fail_what_the_calculation_cannot_see(prepared: Session) -> None:
    """**계산이 먼저이고 사람이 나중이다.**

    세는 항목(이물 · 포장 · 성적서)은 잰 값이 없어 계산에 들어오지 않는다. 그
    결함은 사람이 사유로 적고, 그 순간 측정값이 다 규격 안이어도 불합격이다.
    """
    judged = receive(prepared, _request(nonconformity_code=_FOREIGN_REASON))

    assert judged.result == codes.JUDGMENT_FAILED
    assert judged.nonconformity_code == _FOREIGN_REASON
    assert prepared.query(Lot).count() == 0


# ── 받지 않는 것 ────────────────────────────────────────────────────────────


def test_a_material_group_with_no_standard_is_refused(prepared: Session) -> None:
    """**감사 W-3 이 연 자리다.**

    운영자가 새 자재군을 만들고 기준을 한 줄도 넣지 않으면 「아무것도 재지 않고
    합격」이 되고, 그 로트는 아무 근거 없이 재고가 된다. 검사가 아니라 그냥
    통과이므로 받지 않는다.
    """
    add_code(prepared, codes.MATERIAL_GROUP, "금속")
    prepared.flush()
    prepared.add(make_item(codes.RAW_MATERIAL, code="RM-99", material_group="금속"))
    prepared.flush()

    with pytest.raises(RefusedInspection, match="기준이 한 줄도 없다"):
        receive(prepared, _request(item_code="RM-99", measurements=()))

    assert prepared.query(Lot).count() == 0


def test_a_missing_measurement_is_refused(prepared: Session) -> None:
    """재야 하는 항목을 빠뜨리면 판정의 근거가 반쪽이다."""
    with pytest.raises(RefusedInspection, match=_MOISTURE):
        receive(prepared, _request(measurements=(Measurement(_GRAIN, 30.0),)))


def test_measuring_something_the_standard_does_not_ask_for_is_refused(
    prepared: Session,
) -> None:
    """**분말에 점도를 재지 않는다** — 그 무리의 기준에 없는 항목은 받지 않는다."""
    add_code(prepared, codes.INSP_ITEM, "점도")
    prepared.flush()

    with pytest.raises(RefusedInspection, match="점도"):
        receive(
            prepared,
            _request(
                measurements=(
                    Measurement(_GRAIN, 30.0),
                    Measurement(_MOISTURE, 0.3),
                    Measurement("점도", 3000.0),
                )
            ),
        )


def test_a_finished_good_is_refused_at_the_incoming_gate(prepared: Session) -> None:
    """관문 1 이 보는 것은 원자재뿐이다."""
    prepared.add(make_item(codes.FINISHED_GOODS, code="FG-01"))
    prepared.flush()

    with pytest.raises(RefusedInspection, match="원자재"):
        receive(prepared, _request(item_code="FG-01"))


def test_a_customer_cannot_deliver_material(prepared: Session) -> None:
    """고객사에게 자재를 받지는 않는다."""
    prepared.add(make_partner(codes.CUSTOMER, code="CUS-01"))
    prepared.flush()

    with pytest.raises(RefusedInspection, match="공급사가 아니다"):
        receive(prepared, _request(supplier_code="CUS-01"))


# ── 같은 품목·같은 날에 둘이 동시에 들어오면 (감사 W-2) ────────────────────


def _hold_the_numbering_lock(engine: Engine, item_id: int) -> Connection:
    """다른 연결이 그 품목의 번호 잠금을 쥐고 **놓지 않는다.**

    자문 잠금은 MVCC 와 무관하게 연결을 건너 보이므로, 이쪽 트랜잭션이 아직
    커밋하지 않은 데이터를 저쪽이 못 보는 것과 상관없이 겨룰 수 있다.
    """
    other = engine.connect()
    other.execute(
        text("SELECT pg_advisory_xact_lock(:key, :item)"),
        {"key": locks.LOT_NUMBER, "item": item_id},
    )
    return other


def test_numbering_makes_a_second_writer_wait(prepared: Session, engine: Engine) -> None:
    """**번호를 짓는 코드가 실제로 줄을 서는가.**

    한 트랜잭션에 묶였다는 것만으로는 갱신 유실을 막지 못한다 — 둘이 같은 날의
    마지막 번호를 **동시에 읽으면** 같은 번호를 짓는다. 유일키가 그 사고를 막긴
    하지만 막는 방식이 「둘째가 터진다」라, 검사원에게는 이유 없는 실패로 보인다.

    **채번 함수를 직접 부른다.** 잠금 원시연산만 재면 함수에서 잠금을 빼도
    테스트가 초록이다 — 실제로 그렇게 써 두었다가 돌연변이가 아무것도 물지
    않는 것을 보고 고친 자리다.
    """
    item = prepared.query(Item).filter_by(code="RM-01").one()
    other = _hold_the_numbering_lock(engine, item.id)

    try:
        prepared.execute(text("SET LOCAL lock_timeout = '300ms'"))
        with pytest.raises(OperationalError):
            _next_lot_number(prepared, item, RECEIVED)
    finally:
        other.close()


def test_another_item_does_not_wait(prepared: Session, engine: Engine) -> None:
    """**품목이 다르면 서로 기다릴 이유가 없다.**

    잠금을 키 하나로 걸면 창고 전체가 한 줄로 서고, 그것은 옳지만 느리다.
    둘째 키에 품목을 넣은 이유가 이것이며, 이 테스트가 그 좁힘을 지킨다.
    """
    item = prepared.query(Item).filter_by(code="RM-01").one()
    other = _hold_the_numbering_lock(engine, item.id + 1)

    try:
        prepared.execute(text("SET LOCAL lock_timeout = '300ms'"))

        assert _next_lot_number(prepared, item, RECEIVED) == "RM-01-260921-01"
    finally:
        other.close()


def test_a_receipt_line_cannot_name_someone_elses_judgement(prepared: Session) -> None:
    """**원장 줄이 가리키는 검사가 그 로트를 만든 검사여야 한다.**

    표 18 이 설 때는 로트가 검사를 몰라 이것을 묶을 수 없었고 미결로 들어 두었다.
    로트가 자기를 만든 검사를 가리키게 된 지금, 원장이 **쌍으로** 가리켜 그 한
    겹이 닫힌다 — 둘을 따로 가리키면 둘 다 실재한다는 것까지만 증명된다.
    """
    first = receive(prepared, _request())
    second = receive(prepared, _request(supplier_lot_number="SL-2026-0002"))

    # **그 로트의 입고 줄을 비우고 잰다.** 두면 「로트 하나에 입고 줄 하나」가
    # **먼저** 물어, 이 테스트가 통과하면서도 짝이 맞는지는 한 번도 묻지 않게
    # 된다 — 돌연변이를 돌려 아무것도 물지 않는 것을 보고 고친 자리다.
    prepared.query(StockLedgerEntry).filter_by(lot_id=first.lot_id).delete()
    prepared.flush()

    prepared.add(
        StockLedgerEntry(
            lot_id=first.lot_id,
            txn_type=codes.TXN_PURCHASE_RECEIPT,
            quantity=1.0,
            occurred_at=datetime(2026, 9, 21, 10, 0),
            # 실재하는 검사이지만 **저 로트를 만든 검사가 아니다.**
            inspection_id=second.inspection_id,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()
