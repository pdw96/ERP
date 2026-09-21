"""측정값 줄 — 조각 9.

여기서 검사하는 것은 두 가지다.

**① 분말에 점도를 재지 않는다.** 자재군 축이 연 것을 한 겹 아래에서 닫는
자리다 — 품목 → 검사 → 기준이 같은 자재군을 말하도록 외래키 둘이 묶는다.
묶이지 않으면 기준 표에 자재군을 더한 조각이 한 층 아래에서 무효가 된다.

**② 아무것도 걸러 내지 않는 기준이 서지 않는다.** 규격이 둘 다 빈 항목은 재는
항목이 아니므로 잰 줄이 설 수 없고, `NaN` 이 규격에 들어가면 모든 측정값이
합격하므로 그것도 막는다.
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.inspection import Inspection, InspectionMeasurement
from app.db.master import Item, Partner
from app.db.quality import ProcessInspectionStandard
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

INCOMING = "수입"

# 검사받는 품목의 무리와, 그 무리가 갖지 않는 다른 무리.
GROUP = "분체"
OTHER_GROUP = "액상수지"


def _standard(item_code: str, **overrides: object) -> ProcessInspectionStandard:
    fields: dict[str, object] = {
        "process_code": INCOMING,
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
    return ProcessInspectionStandard(**fields)


@pytest.fixture
def prepared(session: Session) -> Session:
    """합격 검사 한 건과, 그 검사가 쓸 수 있는 기준들."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.INSP_ITEM, "입도")
    add_code(session, codes.INSP_ITEM, "이물")
    add_code(session, codes.INSP_ITEM, "공정온도")
    session.flush()

    material = make_item(codes.RAW_MATERIAL, code="RM-01", material_group=GROUP)
    supplier = make_partner(codes.SUPPLIER, code="SUP-01")
    session.add_all([material, supplier])
    session.flush()

    session.add_all(
        [
            # 재는 항목 — 이 무리와 다른 무리에 하나씩.
            _standard("입도"),
            _standard("입도", material_group=OTHER_GROUP),
            # **재지 않는 항목** — 계수라 규격이 비어 있다.
            _standard(
                "이물",
                upper_spec_limit=None,
                lower_spec_limit=None,
                center_line=None,
                unit=None,
            ),
            # 공정검사 기준 — 자재군이 없다.
            _standard("공정온도", process_code="배합", material_group=None),
        ]
    )
    session.add(
        Inspection(
            item_id=material.id,
            item_type=material.item_type,
            material_group=material.material_group,
            supplier_id=supplier.id,
            supplier_type=supplier.partner_type,
            supplier_lot_number="SL-2026-0001",
            quantity=500.0,
            judged_at=datetime(2026, 9, 21, 9, 0),
            judged_by="검사원 1",
            result=codes.JUDGMENT_PASSED,
        )
    )
    session.flush()
    return session


def _inspection(session: Session) -> Inspection:
    return session.query(Inspection).one()


def _measurement(session: Session, **overrides: object) -> InspectionMeasurement:
    """제약을 통과하는 측정 줄 하나. 넘긴 값만 달라진다."""
    fields: dict[str, object] = {
        "inspection_id": _inspection(session).id,
        "process_code": INCOMING,
        "item_code": "입도",
        "material_group": GROUP,
        "measured_value": 30.0,
        "applied_upper_spec": 50.0,
        "applied_lower_spec": 10.0,
    }
    fields.update(overrides)
    return InspectionMeasurement(**fields)


# ── 줄이 선다 ───────────────────────────────────────────────────────────────


def test_a_measurement_pins_the_spec_it_was_judged_against(prepared: Session) -> None:
    """**판정 시점의 규격을 박아 둔다** — 파생값 금지의 그 예외다."""
    prepared.add(_measurement(prepared))
    prepared.flush()

    row = prepared.query(InspectionMeasurement).one()
    assert row.measured_value == 30.0
    assert (row.applied_lower_spec, row.applied_upper_spec) == (10.0, 50.0)


def test_the_pinned_spec_survives_a_change_to_the_standard(prepared: Session) -> None:
    """**기준이 바뀌어도 그때 그 판정은 그대로 남는다.**

    규격은 고객이 정하고 바뀐다. 합격 여부만 저장했다면 규격이 바뀐 뒤에 옛
    검사를 열었을 때 기록이 자기모순을 일으킨다 — 「측정값 30 · 합격」인데 지금
    규격으로 재계산하면 불합격이 나온다.
    """
    prepared.add(_measurement(prepared))
    prepared.flush()

    standard = (
        prepared.query(ProcessInspectionStandard)
        .filter_by(item_code="입도", material_group=GROUP)
        .one()
    )
    # 고객이 규격을 조인다 — 이 측정값 30 은 **지금 기준으로는 불합격**이다.
    standard.lower_spec_limit = 31.0
    standard.center_line = 35.0
    prepared.flush()

    row = prepared.query(InspectionMeasurement).one()
    # 박아 둔 값은 따라가지 않는다 — 그것이 이 칸이 있는 이유다.
    assert row.applied_lower_spec == 10.0
    assert row.measured_value > row.applied_lower_spec


def test_one_item_is_measured_once_per_inspection(prepared: Session) -> None:
    """두 줄이 서면 어느 값으로 판정했는지 말할 수 없다."""
    prepared.add(_measurement(prepared))
    prepared.flush()

    prepared.add(_measurement(prepared, measured_value=31.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 분말에 점도를 재지 않는다 ───────────────────────────────────────────────


def test_a_standard_from_another_material_group_is_refused(prepared: Session) -> None:
    """**자재군 축이 연 것을 여기서 닫는다.**

    `(입도 × 액상수지)` 는 실재하는 기준이다. 다만 이 검사가 받은 것은 분체이고,
    검사가 자기 품목에서 자재군을 받아 들고 있으므로 **다른 무리의 기준은 가리킬
    수 없다.** 이 묶음이 없으면 기준 표에 자재군을 더한 조각이 한 층 아래에서
    무효가 된다.
    """
    prepared.add(_measurement(prepared, material_group=OTHER_GROUP))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_process_standard_cannot_be_measured_here(prepared: Session) -> None:
    """**공정을 못박는 CHECK 가 없어도 공정검사 기준은 가리킬 수 없다.**

    기준 표에 「자재군이 있다 ⇔ 수입」이 양방향으로 걸려 있고, 이 줄은 자재군을
    **반드시 들고** 기준을 가리킨다. 그래서 가리킬 수 있는 것은 자재군이 있는
    줄, 곧 수입 기준뿐이다 — 같은 명제를 CHECK 로 한 번 더 적는 대신 이 테스트가
    그 자리를 지킨다.
    """
    prepared.add(_measurement(prepared, process_code="배합", item_code="공정온도"))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_standard_that_does_not_exist_is_refused(prepared: Session) -> None:
    """기준이 실재함을 DB 가 보증한다 — 없는 항목을 잰 줄은 서지 않는다."""
    add_code(prepared, codes.INSP_ITEM, "점도")
    prepared.flush()

    prepared.add(_measurement(prepared, item_code="점도"))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 아무것도 걸러 내지 않는 기준이 서지 않는다 ─────────────────────────────


def test_an_item_with_no_spec_at_all_cannot_be_measured(prepared: Session) -> None:
    """**규격이 둘 다 빈 항목은 재는 항목이 아니다.**

    수입 기준에서 그런 것은 `이물` · `포장` · `성적서` 이고, 그 셋은
    `nonconformity_attributes` 에서 정확히 **계수** 코드다. 세는 것이지 재는
    것이 아니므로 관리도에 오를 측정값이 없고, 불합격은
    `inspections.nonconformity_code` 로 적힌다.

    조용히 합격시키면 「아무것도 걸러 내지 않는 기준」이 된다. 이 줄이 판정
    시점의 규격을 스스로 들고 있어 **다른 표를 보지 않고** 걸린다.
    """
    prepared.add(
        _measurement(
            prepared, item_code="이물", applied_upper_spec=None, applied_lower_spec=None
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_one_sided_spec_stands(prepared: Session) -> None:
    """**한쪽만 있는 것은 정상이다** — 수분은 상한만, 접착력은 하한만 본다.

    앞의 테스트가 막는 것은 「둘 다 없음」이지 「한쪽만 있음」이 아니다. 둘을
    가르지 않으면 시드의 기준 절반이 잴 수 없는 항목이 된다.
    """
    prepared.add(_measurement(prepared, applied_lower_spec=None))
    prepared.flush()

    assert prepared.query(InspectionMeasurement).one().applied_upper_spec == 50.0


@pytest.mark.parametrize(
    ("column", "other"),
    [
        ("applied_upper_spec", "applied_lower_spec"),
        ("applied_lower_spec", "applied_upper_spec"),
    ],
)
def test_a_spec_cannot_be_nan(prepared: Session, column: str, other: str) -> None:
    """**규격에 `NaN` 이 들어가면 모든 측정값이 합격한다.**

    서로의 순서를 보는 CHECK 는 이것을 막지 못한다 — `NaN > 하한` 이 참이라 줄이
    그대로 선다. 그리고 판정하는 쪽에서 `측정값 <= 상한` 이 **언제나 참**이 되어,
    규격이 있는 것처럼 보이는데 아무것도 걸러 내지 않는 기준이 된다.

    **반대쪽을 비워 둔다.** 둘 다 채우면 하한이 `NaN` 인 경우를 순서 CHECK 가
    대신 잡아(`50 > NaN` 이 거짓이다) 이 테스트가 통과하면서도 `is_finite()` 가
    서 있는지는 묻지 않게 된다 — 그 제약을 빼는 돌연변이를 돌려 확인한 자리다.
    """
    prepared.add(_measurement(prepared, **{column: float("nan"), other: None}))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_spec_pair_cannot_stand_upside_down(prepared: Session) -> None:
    """거꾸로 선 규격은 터지지 않고 **조용히 틀린 판정**을 만든다."""
    prepared.add(_measurement(prepared, applied_upper_spec=10.0, applied_lower_spec=50.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_the_measured_value_must_be_a_number(prepared: Session, bad: float) -> None:
    """측정값에 `NaN` 이 들어가면 규격과의 비교가 전부 거짓이 된다.

    합격도 불합격도 나오지 않는 줄이라 판정이 멈춘다. **하한은 걸지 않는다** —
    음수를 재는 항목이 있을 수 있으므로 `is_finite()` 만 단독으로 선다.
    """
    prepared.add(_measurement(prepared, measured_value=bad))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_negative_measurement_stands(prepared: Session) -> None:
    """음수는 막지 않는다 — 재는 것에 따라 음수가 정상인 항목이 있다."""
    prepared.add(_measurement(prepared, measured_value=-5.0, applied_lower_spec=-10.0))
    prepared.flush()

    assert prepared.query(InspectionMeasurement).one().measured_value == -5.0


# ── 검사 쪽의 결속 ──────────────────────────────────────────────────────────


def test_an_inspection_carries_the_material_group_of_its_item(prepared: Session) -> None:
    """검사의 자재군은 **품목이 아는 사실**이지 따로 넣는 값이 아니다."""
    item = prepared.query(Item).filter_by(code="RM-01").one()

    assert _inspection(prepared).material_group == item.material_group


def test_an_inspection_cannot_claim_another_material_group(prepared: Session) -> None:
    """품목과 검사가 다른 무리를 말하면 그 사슬이 끊긴다 — 외래키가 막는다."""
    item = prepared.query(Item).filter_by(code="RM-01").one()
    supplier = prepared.query(Partner).filter_by(code="SUP-01").one()

    prepared.add(
        Inspection(
            item_id=item.id,
            item_type=item.item_type,
            material_group=OTHER_GROUP,
            supplier_id=supplier.id,
            supplier_type=supplier.partner_type,
            supplier_lot_number="SL-2026-0002",
            quantity=100.0,
            judged_at=datetime(2026, 9, 21, 10, 0),
            judged_by="검사원 1",
            result=codes.JUDGMENT_PASSED,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()
