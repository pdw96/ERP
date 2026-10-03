"""앱이 뜰 때 현장 시계를 묻는다 — **믿을 수 없으면 뜨지 않는다**(ADR 0019).

세 가지를 차례로 묻는다 —

1. 현장 시간대가 설정돼 있고 아는 이름인가
2. 그 시간대에 지금 이후의 오프셋 전환이 없는가 — 벽시계가 거꾸로 가지 않는가
3. **저장된 가장 늦은 시각이 현장의 지금보다 뒤가 아닌가** — 미래에 적힌
   줄은 시계의 바탕이 갈렸다는 뜻이다. 이 결정 전의 쓰기 경로는 컨테이너의
   지역 시각을 적었으므로, 현장이 컨테이너보다 뒤에 있으면 처음 바꾸는 날
   여기 걸린다. 무엇을 고칠지는 사람이 정한다

**이 가드가 못 보는 부류**(W-6 ③): 미래가 아닌 쪽으로 어긋난 시각 — 현장이
컨테이너보다 앞선 쪽(UTC → 서울)은 옛 줄이 더 이를 뿐이라 순서가 깨지지 않고,
그래서 묻지 않는다. 그리고 앱이 떠 있는 동안 시계가 거꾸로 가는 것 — 묻는
것은 뜰 때 한 번이다.
"""

from datetime import datetime

from sqlalchemy import func, select, union_all
from sqlalchemy.orm import Session

from app.core import clock
from app.db.inspection import Inspection
from app.db.inventory import PurchaseReturn, StockLedgerEntry

# 쓰기 경로가 「지금」을 적는 칸 — 새 칸이 생기면 여기 더한다.
_STAMPED = (Inspection.judged_at, PurchaseReturn.returned_at, StockLedgerEntry.occurred_at)


def latest_stamp(session: Session) -> datetime | None:
    """저장된 시각 가운데 가장 늦은 것."""
    stamps = union_all(
        *(select(func.max(column).label("at")) for column in _STAMPED)
    ).subquery()
    latest: datetime | None = session.scalar(select(func.max(stamps.c.at)))
    return latest


def assert_the_site_clock_holds(session: Session, now: datetime | None = None) -> None:
    """현장 시계를 믿을 수 있는지 묻는다 — 아니면 `clock.SiteClockError`."""
    clock.must_not_reverse(clock.site_zone())
    current = now or clock.now()
    latest = latest_stamp(session)
    if latest is not None and latest > current:
        raise clock.SiteClockError(
            f"저장된 가장 늦은 시각({latest})이 현장의 지금({current})보다 뒤다"
            " — 시계의 바탕이 갈렸다. 시간대 설정이나 그 줄을 사람이 본다(ADR 0019)"
        )
