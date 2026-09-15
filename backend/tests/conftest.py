"""테스트가 붙는 데이터베이스.

**실제 PostgreSQL 에 붙는다.** SQLite 로 대신하면 이 설계가 제약에 기대는
자리(복합 외래키 · CHECK · 부분 인덱스)를 검증할 수 없고, 「숫자 칸에 글자를
넣으면 그냥 들어간다」는 차이가 테스트를 통과시켜 버린다.

DB 가 없으면 **건너뛰지 않고 실패한다.** 건너뛴 테스트는 통과한 것처럼 보이고,
그것이 이 저장소에서 가장 비싼 거짓말이다.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import create_db_engine, create_session_factory

# 개발용 DB 를 밟지 않도록 테스트는 자기 URL 을 따로 받는다.
TEST_DATABASE_URL = os.environ.get(
    "ERP_TEST_DATABASE_URL",
    "postgresql+psycopg://erp:erp@localhost:5432/erp_test",
)


@pytest.fixture(autouse=True)
def guard_against_the_app_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트가 **앱의 기본 DB 에 붙는 것을 구조적으로 막는다.**

    이 가드가 없어서 결함 하나가 로컬을 통과하고 CI 에서야 잡혔다.
    `migrations/env.py` 가 부르는 쪽이 준 URL 을 설정 기본값으로 덮어썼는데,
    개발자의 로컬에는 그 이름의 DB(`erp`)가 있었으므로 **잘못된 DB 에 붙고도
    성공했다.** CI 에는 `erp_test` 뿐이라 거기서 터졌다.

    닿을 수 없는 값으로 덮어 두면 같은 종류의 실수가 로컬에서 곧바로 드러난다
    — 「환경에 따라 다르게 도는 테스트」를 없애는 것이 이 가드의 일이다.
    자기 설정값을 보는 테스트는 `monkeypatch` 로 다시 덮으면 된다.
    """
    monkeypatch.setenv(
        "ERP_DATABASE_URL",
        "postgresql+psycopg://guard:guard@127.0.0.1:1/erp_must_not_be_used",
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """테스트 세션 하나가 쓰는 엔진."""
    eng = create_db_engine(TEST_DATABASE_URL)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - 환경 문제이지 코드 문제가 아니다
        pytest.fail(
            f"테스트 데이터베이스에 붙지 못했다: {TEST_DATABASE_URL}\n"
            f"  {type(exc).__name__}: {exc}\n"
            "  `docker compose up -d postgres` 로 띄우고 erp_test 를 만든다.",
            pytrace=False,
        )
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """세션 공장."""
    return create_session_factory(engine)
