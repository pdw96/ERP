"""SQLAlchemy 선언 기반(base)과 엔진 · 세션.

표의 정의는 여기에 두지 않는다. 여기 있는 것은 **모든 표가 함께 서는 자리**
뿐이다.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """모든 표의 뿌리."""


def create_db_engine(url: str | None = None) -> Engine:
    """엔진 하나를 만든다. `url` 을 주면 그것을 쓰고, 없으면 설정에서 읽는다.

    **격리 수준을 박는다.** 로트 번호를 짓는 구간은 자문 잠금을 잡은 **뒤에**
    그날의 마지막 번호를 읽는데, 그 순서가 뜻을 갖는 것은 READ COMMITTED 가
    문장마다 새 스냅샷을 잡기 때문이다. REPEATABLE READ 에서는 기다렸다 깨어난
    쪽이 **잠그기 전의 스냅샷**을 그대로 읽어 같은 번호를 짓고, 잠금이 없애려던
    바로 그 실패(둘째가 유일키에 터진다)로 되돌아간다 — 실제로 재현된 자리다.

    기본값이 READ COMMITTED 라 오늘은 같은 동작이지만, 기본값은 서버 설정 한
    줄로 뒤집힌다(`ALTER DATABASE … SET default_transaction_isolation`). **적어
    두기만 하고 강제하지 않는 규칙을 만들지 않는다** — 전제를 코드에 박는다.
    """
    #
    # **파라미터를 예외 문자열에 싣지 않는다** (감사 ⑰ NC-164). SQLAlchemy 는
    # `StatementError` 에 `[SQL: …] [parameters: {…}]` 를 붙이는데, 이 엔드포인트에서
    # 가장 있을 법한 500 이 제약 위반이라 그것은 예외 경로가 아니라 **주 경로**다.
    # 한때 500 처리기가 그 예외를 `exc_info` 로 통째로 찍어 요청 본문의 값 전부가
    # 로그에 실렸다. 지금 DB 오류는 SQLSTATE 와 제약 이름만 찍는 처리기가 받는데
    # (`app/api/app.py`, 감사 ㉚), 이 칸은 **엔진이 짓는 모든 문자열**에 걸리므로
    # 그 처리기 밖에서 예외가 찍히는 날을 위해 그대로 둔다 — DB 가 아닌
    # `StatementError` 와, 다른 예외에 연쇄된 DB 오류가 그 자리다.
    #
    # **값을 로그에 여는 조건은 판정이 아니다.** 「판정이 오는 날 열린다」고 적혀
    # 있었는데 판정은 ⑲(`audit-secrets`)에서 이미 왔고, 그 답은 여는 조건이 보존 기간 ·
    # 접근 제어 · 마스킹 셋이라는 것이었다 — 그 문장을 믿으면 셋 중 하나도 없는
    # 로그에 실명을 연다(감사 ㉜ NC-221). 그 조건은 `docs/audit/회차-기록.md` 의 ⑲ 절이
    # 든다 — 여기 두 벌로 적지 않는다.
    return create_engine(
        url or get_settings().database_url,
        future=True,
        isolation_level="READ COMMITTED",
        hide_parameters=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """세션 공장을 만든다."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """트랜잭션 하나를 연다 — 터지면 아무것도 남지 않는다.

    시드도 같은 모양이다(그쪽은 `engine.begin()` 을 직접 쓴다). 「반쯤 채워짐」
    이라는 상태를 없애는 것이 목적이며, PostgreSQL 에는 지우고 다시 시작할
    파일이 없기 때문이다.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
