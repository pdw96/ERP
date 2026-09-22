"""생산 기준정보 — 근무형태와 비가동 구간.

**365행이 아니라 연 몇 행이다.** 24시간 가동이 캘린더를 두 조 + 예외 목록으로
줄였다 — 기준정보는 공정 조건을 알면 작아진다.
"""

from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference, is_present


class ShiftPattern(Base):
    """근무형태 — 현장 주간 · 현장 야간 · 사무.

    **실사 창은 여기서 파생된다.** 두 근무가 겹치는 구간이 실사가 가능한
    시간이고, 그것은 칸이 아니라 계산이다 — 저장하면 근무 시간을 고쳤을 때
    둘이 갈린다.

    야간조는 끝 시각이 시작보다 이르다(21:00 → 09:00). 자정을 넘는 것이
    정상이므로 `ends_at > starts_at` 을 강제하지 않는다.
    """

    __tablename__ = "shift_patterns"
    __table_args__ = (
        *code_reference(
            group_column="group_code",
            code_column="code",
            group_code=codes.SHIFT,
            name="shift_pattern",
        ),
        CheckConstraint("starts_at <> ends_at", name="ck_shift_pattern_has_length"),
    )

    group_code: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=codes.SHIFT, server_default=codes.SHIFT
    )
    code: Mapped[str] = mapped_column(String(30), primary_key=True)

    starts_at: Mapped[time] = mapped_column(Time)
    ends_at: Mapped[time] = mapped_column(Time)
    # 현장인가 사무인가. 실사 창은 둘이 겹치는 구간이고, 생산이 서는 것은
    # 현장 쪽이다.
    on_site: Mapped[bool] = mapped_column(Boolean)


class NonWorkingPeriod(Base):
    """비가동 구간 — 명절과 설비 보전.

    24시간 가동이라도 설비는 선다. 실사일의 생산 정지처럼 **규칙에서 파생되는
    것은 여기 적지 않는다** — 사람이 적는 것은 규칙으로 낼 수 없는 예외뿐이다.

    날짜를 가지므로 기준정보 SQL 에 넣을 수 없다(「오늘」이 나오면 파이썬).
    **표만 세우고 끝낸 단계였다** — 채우는 쪽은 아직 서지 않았다.
    """

    __tablename__ = "non_working_periods"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_non_working_period_order"),
        CheckConstraint(is_present("reason"), name="ck_non_working_period_reason"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(100))
