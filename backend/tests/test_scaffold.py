"""가설공사가 실제로 서 있는지 본다.

표는 아직 하나도 없다. 여기서 확인하는 것은 **관리 수단이 도는가**뿐이다 —
설정을 읽고, DB 에 붙고, 트랜잭션이 터졌을 때 아무것도 남지 않는가.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import session_scope


def test_settings_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """설정은 코드가 아니라 환경에서 온다 — 시크릿을 코드에 쓰지 않기 위해서다."""
    monkeypatch.setenv("ERP_DATABASE_URL", "postgresql+psycopg://a:b@elsewhere:5432/x")
    monkeypatch.setenv("ERP_SEED_ENABLED", "true")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://a:b@elsewhere:5432/x"
    assert settings.seed_enabled is True


def test_seeding_is_off_unless_someone_turns_it_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """운영에서 자동 시드는 사고이지 편의가 아니다 — 기본값이 꺼짐이어야 한다."""
    monkeypatch.delenv("ERP_SEED_ENABLED", raising=False)

    assert Settings().seed_enabled is False


def test_the_database_is_postgresql(engine: Engine) -> None:
    """SQLite 로 대신하지 않는다 — 제약에 기대는 설계라 엔진이 곧 검증 수단이다."""
    assert engine.dialect.name == "postgresql"


def test_a_failed_transaction_leaves_nothing_behind(
    engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    """시드가 중간에 터지면 「반쯤 채워짐」이 남으면 안 된다.

    PostgreSQL 에는 지우고 다시 시작할 파일이 없다. 반쯤 채워진 데이터베이스는
    「비어 있지 않다」로 판정되어 다시는 시드되지 않고, 고장난 채로 굳는다.
    """
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS scaffold_probe"))
        conn.execute(text("CREATE TABLE scaffold_probe (n integer)"))

    with (
        pytest.raises(RuntimeError, match="시드가 중간에 터졌다"),
        session_scope(session_factory) as session,
    ):
        session.execute(text("INSERT INTO scaffold_probe (n) VALUES (1)"))
        raise RuntimeError("시드가 중간에 터졌다")

    with engine.connect() as conn:
        remaining = conn.execute(text("SELECT count(*) FROM scaffold_probe")).scalar_one()
    assert remaining == 0, "터진 트랜잭션이 줄을 남겼다 — 롤백이 서지 않았다"

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE scaffold_probe"))
