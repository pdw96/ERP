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

import app.db  # noqa: F401  — 모델 모듈을 불러들여 metadata 를 채운다
from app.db.base import Base, create_db_engine, create_session_factory

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


@pytest.fixture(scope="session")
def tables(engine: Engine) -> Iterator[None]:
    """표를 세운다.

    **지금은 모델에서 직접 만든다** (`create_all`). 마이그레이션은 조각 7에서
    하나로 굽기 때문이며, 그 조각이 서면 **마이그레이션이 만든 표와 모델이
    같은지를 견주는 테스트**가 여기 붙어야 한다 — 그때까지 이 픽스처는
    「모델이 말하는 표」만 보증하고 「마이그레이션이 만드는 표」는 보증하지
    않는다.
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine: Engine, tables: None) -> Iterator[Session]:
    """테스트 하나가 쓰는 세션 — 끝나면 통째로 되돌린다.

    바깥 트랜잭션을 열고 그 안에서 돌린 뒤 롤백하므로, 테스트끼리 서로가 넣은
    줄을 보지 않는다. 표를 매번 다시 만드는 것보다 빠르고, 「앞 테스트가 남긴
    줄 때문에 통과하는」 테스트를 막는다.
    """
    connection = engine.connect()
    transaction = connection.begin()
    # **SAVEPOINT 로 합류한다.** 그냥 바인딩하면 세션이 제 트랜잭션을 되돌릴 때
    # (제약이 물어 `IntegrityError` 가 날 때마다 그렇다) 바깥 트랜잭션까지 함께
    # 무효가 되고, teardown 의 롤백이 터진다 — 제약을 검사하는 테스트가
    # 통과하고도 오류로 끝난다.
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
