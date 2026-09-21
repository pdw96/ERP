"""쓰기 경로 — 조각 11. **합격이 로트를 만든다.**

표 넷이 선 뒤 이 조각이 하는 일은 **그 표들을 한 트랜잭션으로 묶는 것**이다.
그래서 여기서 검사하는 것은 칸이 아니라 —

- **판정이 계산되는가** (원칙 ③ — 사람이 넣는 것은 측정값뿐)
- **불합격이 로트를 만들지 못하는가** (원칙 ①)
- **로트와 원장 줄이 함께 들어가거나 함께 없는가** (성공기준 ③)
- **같은 품목·같은 날에 둘이 동시에 들어와도 번호가 겹치지 않는가** (감사 W-2)
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core import codes, locks
from app.db.code_attributes import NonconformityAttribute, NonconformityStageRule
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item, Partner
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


def plant_master_data(session: Session) -> None:
    """시드와 같은 모양의 최소 기준정보 — 분체 하나가 항목 셋을 받는다.

    **픽스처가 아니라 함수다.** 진짜 `session_scope` 를 지나가는 검사는 자기
    트랜잭션을 **커밋해야** 하므로 통째로 롤백하는 세션 픽스처를 쓸 수 없다.
    그쪽에서 기준정보를 따로 심으면 목록이 두 벌이 되고, 두 벌은 갈린다.
    """
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


@pytest.fixture
def prepared(session: Session) -> Session:
    """그 기준정보가 심긴 세션 — 테스트가 끝나면 통째로 되돌아간다."""
    plant_master_data(session)
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


# ── 멱등 — **막지 않기로 한 결정을 검사가 든다** (NC-67) ───────────────────
#
# `docs/schema.md` 미결이 「막지 않는다」를 **대가와 함께** 적었다: 유일키는
# 분할 납품을 함께 막고, 잘못 선 입고를 되돌릴 길은 이 조각에 없다. 그 결정이
# 산문 한 줄에만 서 있으면 **다음 사람이 유일키를 더할 때 아무 검사도 물지
# 않는다** — 갈래 둘이 그 자리를 든다.


def test_the_same_request_twice_makes_two_lots(prepared: Session) -> None:
    """**오늘의 동작을 못박는다** — 글자까지 같은 요청 둘이 로트 둘을 만든다.

    이것이 NC-67 이 말한 대가다. 막지 않기로 했으므로 **이 검사가 빨개지는
    변경은 그 결정을 뒤집는 변경**이고, 뒤집을 때는 `docs/schema.md` 의 그 줄을
    함께 고쳐야 한다.
    """
    first = receive(prepared, _request())
    second = receive(prepared, _request())

    assert first.lot_number == "RM-01-260921-01"
    assert second.lot_number == "RM-01-260921-02"
    assert prepared.query(Inspection).count() == 2


def test_a_split_delivery_of_the_same_supplier_lot_is_accepted(prepared: Session) -> None:
    """**분할 납품이 막히지 않는다** — 한 공급사 로트가 나뉘어 와도 둘 다 선다.

    `(공급사 × 공급사 로트번호)` 에 유일키를 더하면 중복 제출은 막히지만 **이
    경로가 함께 막힌다.** 그것이 막지 않기로 한 이유이고, 이 갈래가 그 자리에서
    빨개진다 — 「둘째는 그날의 다음 일련을 받는다」를 재는 갈래는 공급사 번호가
    **서로 달라** 그 변경을 통과시킨다.
    """
    receive(prepared, _request(quantity=300.0))
    receive(prepared, _request(quantity=200.0))

    arrived = prepared.query(Inspection).all()
    assert [row.supplier_lot_number for row in arrived] == ["SL-2026-0001"] * 2
    assert sum(row.quantity for row in arrived) == 500.0


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


def test_a_failed_judgement_still_remembers_when_the_material_arrived(
    prepared: Session,
) -> None:
    """**불합격에도 도착일이 남는다** (NC-109).

    도착일이 앉는 자리가 로트뿐이었고 **불합격은 로트를 만들지 않으므로**, 사람이
    보낸 그 값이 불합격에서만 조용히 버려졌다 — 201 로 성공 응답이 나가면서다.
    하필 불합격이 **클레임과 반품의 근거**가 되는 판정이다.

    `judged_at` 이 대신이 되지 못한다는 것을 함께 잰다 — 뒤늦게 적은 입고를
    일부러 받으므로 둘은 갈리고, **갈리는 그 값이 사라지던 것**이다.
    """
    arrived = RECEIVED - timedelta(days=20)
    judged = receive(
        prepared,
        _request(
            received_date=arrived,
            measurements=(Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3)),
        ),
    )

    assert judged.result == codes.JUDGMENT_FAILED
    assert prepared.query(Lot).count() == 0

    inspection = prepared.get(Inspection, judged.inspection_id)
    assert inspection is not None
    assert inspection.received_date == arrived
    # **스무 날이 갈린다.** 이 차이가 사라지던 것이고, `judged_at` 으로는 되짚을
    # 수 없다 — 검사가 얼마나 늦었는지는 어디에도 적혀 있지 않다.
    assert inspection.judged_at.date() != arrived


def test_a_pass_cannot_let_the_two_arrival_dates_drift(prepared: Session) -> None:
    """**같은 사실이 두 표에 살면 갈린다** — 그래서 쌍으로 가리킨다 (원칙 ⑥).

    로트도 도착일을 드는데, 두 칸이 서로를 모르면 한쪽만 고쳐질 수 있다.
    `fk_lot_inspection_received_date` 가 그것을 **데이터베이스에서** 막는다 —
    주석은 규칙이 아니다.
    """
    receive(prepared, _request())
    lot = prepared.query(Lot).one()

    lot.received_date = RECEIVED - timedelta(days=1)
    with pytest.raises(IntegrityError, match="fk_lot_inspection_received_date"):
        prepared.flush()


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


def test_a_material_group_with_nothing_to_measure_is_refused(prepared: Session) -> None:
    """**같은 결정의 한 겹 아래다** — 기준은 있는데 **재는** 기준이 없는 무리.

    위의 가드는 「기준이 0줄」만 본다. 세는 항목(이물 · 포장 · 성적서)만 걸린
    무리는 그것을 통과하고, **측정값 줄이 하나도 없는 합격**이 서서 로트와 입고
    줄을 만든다 — 결정은 넓은데 가드가 한 칸만 보던 자리다.
    """
    add_code(prepared, codes.MATERIAL_GROUP, "금속")
    prepared.flush()
    prepared.add(make_item(codes.RAW_MATERIAL, code="RM-99", material_group="금속"))
    _standard(
        prepared,
        _FOREIGN,
        material_group="금속",
        upper_spec_limit=None,
        lower_spec_limit=None,
        center_line=None,
        unit=None,
    )
    prepared.flush()

    with pytest.raises(RefusedInspection, match="재는 항목이 한 줄도 없다"):
        receive(prepared, _request(item_code="RM-99", measurements=()))

    assert prepared.query(Lot).count() == 0


def test_measuring_the_same_item_twice_is_refused(prepared: Session) -> None:
    """**판정이 요청 순서에 달리면 안 된다.**

    같은 항목이 두 번 오면 `dict` 가 뒤엣것으로 덮는다 — 순서만 뒤집으면 합격과
    불합격이 뒤집히고, 표에는 어느 쪽으로 갈렸는지 흔적이 없다. 측정값 표의
    기본키가 이것을 막도록 되어 있지만 **거기까지 가지 않는다.**
    """
    for first, second in ((30.0, 99.0), (99.0, 30.0)):
        with pytest.raises(RefusedInspection, match=f"두 번 쟀다: {_GRAIN}"):
            receive(
                prepared,
                _request(
                    measurements=(
                        Measurement(_GRAIN, first),
                        Measurement(_GRAIN, second),
                        Measurement(_MOISTURE, 0.3),
                    )
                ),
            )

    assert prepared.query(Inspection).count() == 0


def test_a_reason_sent_with_an_out_of_spec_value_is_refused(prepared: Session) -> None:
    """**사람이 적은 사유를 조용히 삼키지 않는다.**

    계산이 이탈을 하나라도 잡으면 사유는 계산이 고른다. 그때 사람이 보낸 사유를
    읽지도 않고 버리면 「입도가 벗어났는데 이물도 섞여 있었다」가 표 어디에도
    남지 않고, **없는 코드를 보내도 아무 말이 없다.** 사유 칸이 하나인 것은
    설계이므로 둘을 함께 적을 수는 없다 — 그러면 남는 답은 되돌려보내는 것이다.
    """
    out_of_spec = (Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3))

    with pytest.raises(RefusedInspection, match="사유 칸은 하나"):
        receive(
            prepared,
            _request(measurements=out_of_spec, nonconformity_code=_FOREIGN_REASON),
        )

    assert prepared.query(Inspection).count() == 0


def test_a_measured_reason_cannot_be_sent_by_a_person(prepared: Session) -> None:
    """**재는 항목의 판정은 측정값에서만 나온다** (원칙 ③).

    규격 안에 드는 값을 적어 놓고 `입도 이탈` 을 사유로 보내면, 계산은 합격을
    냈는데 **요청 본문이 그것을 불합격으로 덮는다.** 특채가 열린 사유라면
    **규격 안인데 특채**라는 줄까지 선다 — 사람이 적을 수 있는 것은 계산이 보지
    못하는 것, 곧 세는 항목의 결함뿐이다.
    """
    with pytest.raises(RefusedInspection, match="사람이 적을 수 없다"):
        receive(prepared, _request(nonconformity_code=_GRAIN_REASON))

    assert prepared.query(Inspection).count() == 0


def test_a_value_for_a_counted_item_is_refused(prepared: Session) -> None:
    """**세는 항목에는 잰 값이 없다.**

    그 무리의 기준에 있으므로 「기준에 없는 항목」 검사는 지나가고, 규격 두 칸이
    다 빈 측정 줄이 서서 `ck_inspection_measurement_has_a_spec` 가 문다 — **잘
    만들어진 요청 하나가 제약 이름이 담긴 500 으로** 나가던 자리다.
    """
    with pytest.raises(RefusedInspection, match="잰 값을 적을 수 없다"):
        receive(
            prepared,
            _request(
                measurements=(
                    Measurement(_GRAIN, 30.0),
                    Measurement(_MOISTURE, 0.3),
                    Measurement(_FOREIGN, 0.0),
                )
            ),
        )


def test_an_inactive_supplier_cannot_deliver(prepared: Session) -> None:
    """**꺼진 거래처로 새 사실을 만들지 않는다.**

    그 칸은 지난 줄이 가리키는 거래처를 지우지 않으려고 있다. 꺼져 있는데 새
    검사가 서면 그 칸이 아무것도 뜻하지 않게 된다.
    """
    supplier = prepared.query(Partner).filter_by(code="SUP-01").one()
    supplier.is_active = False
    prepared.flush()

    with pytest.raises(RefusedInspection, match="거래가 끝난 공급사"):
        receive(prepared, _request())


def test_an_item_code_too_long_for_the_lot_number_is_refused(prepared: Session) -> None:
    """**우리가 지은 번호가 칸을 넘으면 데이터베이스가 자르려다 터진다.**

    품목 코드는 50자까지 서는데 로트 번호도 50자다 — `-YYMMDD-NN` 이 열 자를
    더하므로 긴 코드의 품목은 **정상으로 서고 그 품목의 모든 합격이 500** 이
    된다. 번호를 짓기 전에 이름으로 말한다.
    """
    long_code = "RM-" + "X" * 45
    prepared.add(make_item(codes.RAW_MATERIAL, code=long_code, material_group=GROUP))
    prepared.flush()

    with pytest.raises(RefusedInspection, match="로트 번호가 칸"):
        receive(prepared, _request(item_code=long_code))

    assert prepared.query(Lot).count() == 0


def test_the_expiry_counts_from_the_day_it_arrived(prepared: Session) -> None:
    """**세는 것은 입고일부터다** — 시드의 `IQ-EXP` 가 그렇게 적는다.

    판정일부터 세면 **검사가 늦어진 만큼 유효기간이 늘어난다.** 뒤늦게 적은 입고
    한 건이 이미 지난 자재를 멀쩡한 재고로 만드는 자리다.
    """
    item = prepared.query(Item).filter_by(code="RM-01").one()
    item.shelf_life_days = 365
    prepared.flush()
    arrived = date.today() - timedelta(days=3)

    receive(prepared, _request(received_date=arrived))

    lot = prepared.query(Lot).one()
    assert lot.expiry_date == arrived + timedelta(days=365)
    # 판정일에서 세었다면 사흘이 더 붙는다.
    assert lot.expiry_date != date.today() + timedelta(days=365)


def test_material_that_already_expired_on_arrival_is_refused(prepared: Session) -> None:
    """**이미 지난 자재가 합격으로 서지 않는다.**

    로트의 CHECK 가 같은 것을 막지만 거기서 나오는 말은 제약 이름이라 500 이
    된다. 「며칠은 남아 있어야 하는가」(`IQ-EXP`)는 **그 값이 어디에도 없어**
    여기서 보지 않는다 — 보는 것은 「이미 지났는가」뿐이다.
    """
    item = prepared.query(Item).filter_by(code="RM-01").one()
    item.shelf_life_days = 30
    prepared.flush()
    long_ago = date.today() - timedelta(days=31)

    with pytest.raises(RefusedInspection, match="이미 지난 날"):
        receive(prepared, _request(received_date=long_ago))

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
