"""「오늘」과 「지금」 — **현장 시간대가 가른다**(ADR 0019).

쓰기 경로가 날짜와 시각을 세는 자리는 여기 하나다. 컨테이너의 지역 시각을
쓰면 컨테이너가 UTC 이고 현장이 서울일 때 하루 아홉 시간 동안 날짜가 하루
어긋나고, 라벨에 찍히는 만료일이 하루 앞당겨진다.

**저장된 시각은 현장의 벽시계 시각이다** — 칸은 시간대 없는 `timestamp`
그대로다. 그래서 벽시계가 거꾸로 가는 시간대는 받지 않는다
(`must_not_reverse`). 거꾸로 가면 나중 사건의 시각이 더 작아져 시각 순서를
보는 트리거가 정상 요청을 막는다.

**값이 없으면 지어내지 않는다.** 설정이 비면 이 모듈은 시각을 내지 않고
이름으로 멈춘다 — 기본값을 두면 그것이 곧 컨테이너의 UTC 를 쓰는 사고다
(`CLAUDE.md` 「없는 값을 지어내지 않는다」).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings

# 앞으로의 오프셋 전환을 찾는 범위와 간격. tz 데이터는 되풀이되는 서머타임을
# 규칙으로 들고 있어 한 해 안에 드러나고, 한 번뿐인 변경은 공표된 것만
# 데이터에 있다 — 그래서 범위는 넉넉히 두고, 간격은 서머타임 한 철보다
# 짧으면 된다.
_LOOK_AHEAD = timedelta(days=365 * 10)
_STEP = timedelta(days=1)


class SiteClockError(RuntimeError):
    """현장 시계를 믿을 수 없다 — 앱은 뜨지 않는다."""


def site_zone() -> ZoneInfo:
    """설정된 현장 시간대. 없거나 모르는 이름이면 멈춘다."""
    name = get_settings().site_timezone
    if not name:
        raise SiteClockError(
            "현장 시간대(ERP_SITE_TIMEZONE)가 없다 — 「오늘」을 셀 수 없다."
            " IANA 이름을 준다(예: Asia/Seoul)"
        )
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise SiteClockError(f"모르는 시간대다: {name!r}") from exc


def now() -> datetime:
    """현장의 지금 — 시간대 없는 벽시계 시각이다. 저장되는 칸과 같은 모양이다."""
    return datetime.now(site_zone()).replace(tzinfo=None)


def today() -> date:
    """현장의 오늘."""
    return now().date()


def must_not_reverse(zone: ZoneInfo, start: datetime | None = None) -> None:
    """**지금 이후에 오프셋이 바뀌는 시간대면 멈춘다** — 지나간 전환은 묻지 않는다.

    늘어나는 전환도 받지 않는다 — 서머타임은 늘었다가 다시 준다. 한 번뿐인
    증가까지 막는 것은 ADR 0019 가 「전환이 있으면」으로 적었기 때문이고, 그런
    현장은 그 ADR 을 대체하는 결정이 받는다.
    """
    moment = start or datetime.now(UTC)
    first = moment.astimezone(zone).utcoffset()
    end = moment + _LOOK_AHEAD
    while moment < end:
        moment += _STEP
        if moment.astimezone(zone).utcoffset() != first:
            raise SiteClockError(
                f"{zone.key} 는 {moment.date()} 무렵 오프셋이 바뀐다 —"
                " 벽시계로 적는 시각이 거꾸로 갈 수 있어 받지 않는다(ADR 0019)"
            )
