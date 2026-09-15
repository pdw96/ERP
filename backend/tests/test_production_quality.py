"""근무형태 · 비가동 구간 · 공정별 검사 기준 — 조각 5."""

from datetime import datetime, time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.production import NonWorkingPeriod, ShiftPattern
from app.db.quality import ProcessInspectionStandard
from tests.factories import add_code


def _standard(**overrides: object) -> ProcessInspectionStandard:
    fields: dict[str, object] = {
        "process_code": "코팅",
        "process_group": codes.PROCESS,
        "item_code": "두께",
        "item_group": codes.INSP_ITEM,
        "upper_spec_limit": 110.0,
        "lower_spec_limit": 90.0,
        "center_line": 100.0,
        "warning_ratio": codes.DEFAULT_WARNING_RATIO,
        "sigma_source": codes.SIGMA_UNDECIDED,
        "unit": "µm",
    }
    fields.update(overrides)
    return ProcessInspectionStandard(**fields)


@pytest.fixture
def prepared(session: Session) -> Session:
    add_code(session, codes.PROCESS, "코팅")
    add_code(session, codes.INSP_ITEM, "두께")
    add_code(session, codes.SHIFT, "현장 주간")
    add_code(session, codes.SHIFT, "현장 야간")
    add_code(session, codes.SHIFT, "사무")
    session.flush()
    return session


# ── 근무형태 ────────────────────────────────────────────────────────────────


def test_the_night_shift_may_cross_midnight(prepared: Session) -> None:
    """야간조는 끝 시각이 시작보다 이르다 (21:00 → 09:00).

    `ends_at > starts_at` 을 강제하면 이 줄이 설 수 없다 — 자정을 넘는 것이
    정상인 표에서 그 제약은 사실을 막는다.
    """
    prepared.add(
        ShiftPattern(code="현장 야간", starts_at=time(21, 0), ends_at=time(9, 0), on_site=True)
    )
    prepared.flush()

    row = prepared.get(ShiftPattern, (codes.SHIFT, "현장 야간"))
    assert row is not None
    assert row.starts_at > row.ends_at


def test_a_shift_cannot_have_zero_length(prepared: Session) -> None:
    """시작과 끝이 같으면 아무도 일하지 않는 근무형태다."""
    prepared.add(
        ShiftPattern(code="사무", starts_at=time(9, 0), ends_at=time(9, 0), on_site=False)
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_audit_window_is_derived_not_stored(prepared: Session) -> None:
    """실사 창 09:00–17:30 은 **두 근무가 겹치는 구간**이지 칸이 아니다.

    저장하면 근무 시간을 고쳤을 때 둘이 갈린다. 표에 그런 칸이 없다는 것을
    여기서 못박는다.
    """
    prepared.add(
        ShiftPattern(code="현장 주간", starts_at=time(9, 0), ends_at=time(21, 0), on_site=True)
    )
    prepared.add(
        ShiftPattern(code="사무", starts_at=time(8, 30), ends_at=time(17, 30), on_site=False)
    )
    prepared.flush()

    columns = {column.name for column in ShiftPattern.__table__.columns}
    assert "audit_window_start" not in columns
    assert "audit_window_end" not in columns

    on_site = prepared.get(ShiftPattern, (codes.SHIFT, "현장 주간"))
    office = prepared.get(ShiftPattern, (codes.SHIFT, "사무"))
    assert on_site is not None and office is not None
    # 겹치는 구간이 실제로 09:00–17:30 이다.
    assert max(on_site.starts_at, office.starts_at) == time(9, 0)
    assert min(on_site.ends_at, office.ends_at) == time(17, 30)


def test_a_shift_code_must_exist_in_the_shift_group(prepared: Session) -> None:
    """근무형태도 공통코드다."""
    prepared.add(
        ShiftPattern(code="휴일조", starts_at=time(9, 0), ends_at=time(18, 0), on_site=True)
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 비가동 구간 ─────────────────────────────────────────────────────────────


def test_a_non_working_period_must_end_after_it_starts(session: Session) -> None:
    """거꾸로 된 구간은 비가동이 아니라 오기다."""
    session.add(
        NonWorkingPeriod(
            starts_at=datetime(2026, 9, 20, 9, 0),
            ends_at=datetime(2026, 9, 19, 9, 0),
            reason="추석",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_non_working_period_needs_a_reason(session: Session) -> None:
    """왜 섰는지 모르는 비가동은 나중에 아무것도 설명하지 못한다."""
    session.add(
        NonWorkingPeriod(
            starts_at=datetime(2026, 9, 19, 9, 0),
            ends_at=datetime(2026, 9, 20, 9, 0),
            reason="　",  # 전각 공백
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# ── 공정별 검사 기준 ────────────────────────────────────────────────────────


def test_sigma_and_its_source_move_together(prepared: Session) -> None:
    """**양방향이다.** σ 가 있으면 출처가 「미정」일 수 없다.

    한쪽만 걸면 다른 쪽으로 샌다 — 숫자는 있는데 어디서 왔는지 모르는 σ 나,
    실측이라 적혔는데 값이 없는 줄이 선다. 그러면 화면의 Cpk 가 진짜인지
    자리표시자인지 아무도 모른다.
    """
    prepared.add(_standard(sigma=1.5, sigma_source=codes.SIGMA_UNDECIDED))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_measured_sigma_cannot_be_missing(prepared: Session) -> None:
    """반대 방향 — 실측이라 적고 값을 비우면 잰 적 없는 것을 쟀다고 적은 것이다."""
    prepared.add(_standard(sigma=None, sigma_source=codes.SIGMA_OBSERVED))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_standard_starts_with_sigma_undecided(prepared: Session) -> None:
    """σ 를 비워 두는 것이 기본이다 — 경고선과 WE 규칙 4 는 σ 없이 돈다."""
    standard = _standard()
    prepared.add(standard)
    prepared.flush()

    assert standard.sigma is None
    assert standard.sigma_source == codes.SIGMA_UNDECIDED
    assert standard.warning_ratio == 0.70


def test_the_warning_line_sits_inside_the_spec(prepared: Session) -> None:
    """계수가 1 이면 경고선이 규격과 같아 경고가 아니다."""
    prepared.add(_standard(warning_ratio=1.5))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_spec_limits_cannot_be_inverted(prepared: Session) -> None:
    """상한이 하한보다 낮으면 합격 구간이 비어 어떤 값도 불합격이다."""
    prepared.add(_standard(upper_spec_limit=90.0, lower_spec_limit=110.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_center_line_cannot_sit_outside_the_spec(prepared: Session) -> None:
    """중심선이 규격 밖이면 「돌아가야 할 목표」가 불합격 구간이다."""
    prepared.add(_standard(center_line=200.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


@pytest.mark.parametrize("field", ["upper_spec_limit", "lower_spec_limit", "center_line"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_spec_cannot_hold_a_number_you_cannot_compare_with(
    prepared: Session, field: str, value: float
) -> None:
    """**규격이 `NaN` 이면 모든 측정값이 합격한다.**

    순서 CHECK 는 이것을 막지 못한다 — `NaN > 하한` 이 참이고 `중심선 <= NaN` 도
    참이라 줄이 그대로 선다. 그리고 판정하는 쪽에서 `측정값 <= 상한` 이 **언제나
    참**이 되어, 규격이 있는 것처럼 보이는데 아무것도 걸러 내지 않는 기준이
    남는다. **불합격이 한 건도 나지 않는 공정은 정상으로 보인다.**
    """
    prepared.add(_standard(**{field: value}))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_one_sided_spec_is_allowed(prepared: Session) -> None:
    """상한만 있는 항목이 있다 — 이물 수나 수분처럼 적을수록 좋은 값이다."""
    prepared.add(_standard(lower_spec_limit=None, center_line=None))

    prepared.flush()


def test_time_variant_is_off_by_default(prepared: Session) -> None:
    """재검사가 다시 보는 것은 **시간이 바꾸는 항목뿐**이다.

    기본이 켜짐이면 만료 재검사가 모든 항목을 다시 보게 되고, 그것은 22판이
    좁혀 둔 범위를 되돌린다.
    """
    standard = _standard()
    prepared.add(standard)
    prepared.flush()

    assert standard.time_variant is False


def test_an_unknown_process_or_item_is_refused(prepared: Session) -> None:
    """기준은 (공정 × 항목)에 붙는다 — 둘 다 공통코드에 있어야 한다."""
    prepared.add(_standard(process_code="존재하지않는공정"))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_measuring_unit_is_not_a_stock_unit(prepared: Session) -> None:
    """mm · cP · ΔE 는 재고 단위와 다른 축이다.

    섞으면 「킬로그램으로 재는 색차」가 적힌다. 그래서 이 칸은 `UOM` 그룹을
    가리키지 않는다.
    """
    standard = _standard(unit="ΔE")
    prepared.add(standard)
    prepared.flush()

    assert standard.unit == "ΔE"


def test_a_warning_ratio_of_one_is_not_a_warning(prepared: Session) -> None:
    """**계수가 1 이면 경고선이 규격과 겹친다.**

    그러면 「규격에 가까워졌는가」를 미리 말하지 못하고, 불합격이 난 뒤에야
    같이 걸린다 — 경고선을 두는 이유가 사라진다. 경계값이라 `<= 1` 과 `< 1` 의
    차이가 조용히 지나가기 쉬운 자리다.
    """
    prepared.add(_standard(warning_ratio=1.0))

    with pytest.raises(IntegrityError):
        prepared.flush()
