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
    """엔진 하나를 만든다. `url` 을 주면 그것을 쓰고, 없으면 설정에서 읽는다."""
    return create_engine(url or get_settings().database_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """세션 공장을 만든다."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """트랜잭션 하나를 연다 — 터지면 아무것도 남지 않는다.

    시드가 이 모양을 쓴다. 「반쯤 채워짐」이라는 상태를 없애는 것이 목적이며,
    PostgreSQL 에는 지우고 다시 시작할 파일이 없기 때문이다.
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
