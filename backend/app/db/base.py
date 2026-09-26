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
    # 500 처리기가 `exc_info` 로 예외를 통째로 찍으므로 요청 본문의 값 전부가
    # (판정자 이름 · 품목 코드 · 공급사 로트번호 · 수량) 로그에 실린다.
    #
    # **그것은 아직 결정된 적이 없다.** 대장이 「로그에 `judged_by`·품목 코드를
    # 실을지」를 `audit-secrets` 가 먼저 판정할 자리로 **등록해 두었는데**, 미뤄 둔
    # 결정이 코드에서 이미 한쪽으로 실행되고 있었다. 판정이 올 때까지 끈다 —
    # 보존 기간도 접근 제어도 마스킹도 아직 하나도 서 있지 않다.
    #
    # 끄면 잃는 것은 **어느 값이 걸렸는가**이고, 남는 것은 SQL 문과 제약 이름이다.
    # 그 판정이 오는 날 「고른 값만 로그 줄에 싣는다」가 열리는 길이다.
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
