"""현장 시계 — 3단계 읽는 조각 A(ADR 0019).

「오늘」과 「지금」은 **현장 시간대가 가른다.** 여기서 재는 것은 —

- 쓰기 경로가 세는 시각이 컨테이너가 아니라 설정된 시간대의 것인가
- 시간대가 없거나 모르는 이름이거나 앞으로 벽시계가 거꾸로 가는 시간대면 멈추는가
- 저장된 가장 늦은 시각이 현장의 지금보다 뒤면 멈추는가
- 그 물음이 **앱이 뜰 때** 도는가 — 뜬 뒤 첫 요청이 아니라
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.app import app
from app.core import clock
from app.db.inspection import Inspection
from app.db.inventory import PurchaseReturn
from app.services.incoming import (
    IncomingInspection,
    Measurement,
    Refusal,
    RefusedInspection,
    receive,
)
from app.services.returns import return_to_supplier
from app.services.site_clock import assert_the_site_clock_holds, latest_stamp
from tests.test_return_path import _back, _failed, planted  # noqa: F401 — 픽스처
from tests.test_write_path import _GRAIN, _MOISTURE


def test_now_is_the_site_wall_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """**컨테이너가 아니라 설정된 시간대의 벽시계다** — 오프셋이 26 시간
    떨어진 두 곳을 견준다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", "Etc/GMT-14")
    ahead = clock.now()
    monkeypatch.setenv("ERP_SITE_TIMEZONE", "Etc/GMT+12")
    behind = clock.now()

    assert abs((ahead - behind) - timedelta(hours=26)) < timedelta(minutes=1)
    assert ahead.tzinfo is None


@pytest.mark.parametrize(
    ("zone", "said"),
    [("", "ERP_SITE_TIMEZONE"), ("Mars/Olympus_Mons", "모르는 시간대")],
    ids=["missing", "unknown"],
)
def test_a_clock_nobody_set_does_not_tell_the_time(
    monkeypatch: pytest.MonkeyPatch, zone: str, said: str
) -> None:
    """**값이 없으면 지어내지 않는다** — 컨테이너의 시각으로 물러서지 않고, 무엇이
    빠졌는지 이름으로 말한다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", zone)

    with pytest.raises(clock.SiteClockError, match=said):
        clock.now()


@pytest.mark.parametrize("zone", ["Etc/GMT-14", "Etc/GMT+12"])
def test_the_gate_draws_today_on_the_site_calendar(
    planted: Session,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    zone: str,
) -> None:
    """**도착일의 「미래」도 현장의 달력으로 가른다.** 두 시간대는 UTC 와 26 시간 떨어져
    있어 어느 시각에 돌려도 적어도 하나는 컨테이너(UTC)와 날짜가 다르다 — 컨테이너의
    오늘로 가르면 그쪽에서 오늘을 거절하거나 내일을 받는다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", zone)

    def arriving(on: date) -> IncomingInspection:
        return IncomingInspection(
            item_code="RM-01",
            supplier_code="SUP-01",
            supplier_lot_number="SL-2026-0001",
            quantity=10.0,
            judged_by="검사원 1",
            received_date=on,
            measurements=(Measurement(_GRAIN, 99.0), Measurement(_MOISTURE, 0.3)),
        )

    receive(planted, arriving(clock.today()))
    with pytest.raises(RefusedInspection) as refused:
        receive(planted, arriving(clock.today() + timedelta(days=1)))
    assert refused.value.code == Refusal.RECEIVED_DATE_IS_IN_THE_FUTURE


@pytest.mark.parametrize("zone", ["Asia/Seoul", "Etc/UTC"])
def test_a_zone_whose_wall_clock_runs_forward_is_taken(zone: str) -> None:
    clock.must_not_reverse(clock.ZoneInfo(zone))


def test_a_zone_whose_wall_clock_turns_back_is_refused() -> None:
    """**서머타임이 있는 시간대는 받지 않는다** — 끝나는 날 벽시계가 한 시간 되돌아가 나중
    사건의 시각이 더 작아진다."""
    with pytest.raises(clock.SiteClockError, match="오프셋이 바뀐다"):
        clock.must_not_reverse(clock.ZoneInfo("America/New_York"))


def test_an_empty_database_has_nothing_from_the_future(session: Session) -> None:
    assert latest_stamp(session) is None
    assert_the_site_clock_holds(session)


def test_a_stamp_later_than_the_site_now_stops_the_clock(planted: Session) -> None:  # noqa: F811
    """**미래에 적힌 줄은 시계의 바탕이 갈렸다는 뜻이다** — 컨테이너 시각으로 적힌 옛 줄이
    현장 시각보다 앞서면 처음 바꾸는 날 순서가 깨진다(ADR 0019)."""
    inspection = planted.get(Inspection, _failed(planted))
    assert inspection is not None

    assert_the_site_clock_holds(planted, now=inspection.judged_at)
    with pytest.raises(clock.SiteClockError, match="보다 뒤다"):
        assert_the_site_clock_holds(planted, now=inspection.judged_at - timedelta(seconds=1))


@pytest.mark.parametrize("zone", ["", "America/New_York"], ids=["missing", "turns-back"])
def test_the_app_does_not_start_on_a_clock_it_cannot_trust(
    monkeypatch: pytest.MonkeyPatch, zone: str
) -> None:
    """**뜰 때 묻는다** — 뜬 뒤 첫 요청이 500 을 받는 것보다 뜨지 않는 쪽이
    고칠 사람에게 빠르다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", zone)

    with pytest.raises(clock.SiteClockError), TestClient(app):
        pass


def test_the_write_paths_stamp_the_site_wall_clock(
    planted: Session,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**검사와 반품이 적는 시각이 현장의 벽시계다** — UTC 와 14 시간 떨어진 곳이라
    컨테이너 시각을 적으면 어느 시각에 돌려도 드러난다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", "Etc/GMT-14")
    inspection = planted.get(Inspection, _failed(planted))
    assert inspection is not None
    returned = return_to_supplier(planted, _back(inspection.id, 1.0))
    document = planted.get(PurchaseReturn, returned.purchase_return_id)
    assert document is not None

    for stamp in (inspection.judged_at, document.returned_at):
        assert abs(clock.now() - stamp) < timedelta(minutes=1)
