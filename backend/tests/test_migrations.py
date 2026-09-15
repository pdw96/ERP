"""마이그레이션이 모델과 같은 표를 만드는가.

자동 생성은 CHECK 식을 **실행 시점 방언으로 문자열로 구워 박는다.** 그래서
모델을 고치고 마이그레이션을 다시 내지 않으면, 또는 마이그레이션을 손으로
고치면, 둘이 조용히 갈린다. 갈린 쪽은 규칙을 잃는데 아무도 모른다.

그래서 **두 스키마를 실제로 만들어 견준다** — 하나는 마이그레이션으로, 하나는
모델로. 컬럼과 제약 정의가 한 글자라도 다르면 여기서 걸린다. 읽기 좋으라고
CHECK 식을 줄바꿈하는 것조차 이 테스트가 잡는다.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.core.alembic_url import apply_database_url, escaped_for_configparser
from app.core.config import get_settings
from app.db.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config("postgresql+psycopg://x/y"))


def test_the_migration_history_is_a_single_line() -> None:
    """머리가 둘이면 어느 쪽이 진실인지 아무도 모른다."""
    heads = _script_directory().get_heads()

    assert len(heads) <= 1, f"마이그레이션 머리가 둘 이상이다: {heads}"


def test_the_url_is_not_written_in_alembic_ini() -> None:
    """URL 을 `alembic.ini` 에 적지 않는다 — 두 벌이면 반드시 갈린다.

    `env.py` 가 설정에서 읽으므로 ini 에 적으면 같은 값이 두 곳에 산다.
    """
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    assert config.get_main_option("sqlalchemy.url", None) in (None, "")


def test_alembic_connects_to_the_url_it_is_given(engine: Engine) -> None:
    """**부르는 쪽이 준 URL 이 이긴다.** 설정은 기본값이지 우선값이 아니다.

    이 테스트가 CI 에서 처음 터졌다. `env.py` 가 준 URL 을 설정값으로 덮어써
    앱의 기본 DB 로 붙고 있었는데, 개발자의 로컬에 그 이름의 DB 가 있어서
    **잘못된 DB 에 붙고도 성공했다.** `conftest` 의 가드가 이제 그 함정을
    로컬에서도 드러낸다 — 앱 기본 URL 은 닿을 수 없는 값으로 덮여 있으므로,
    이 테스트가 그리로 붙으면 곧바로 터진다.

    오류 없이 끝나는 것 자체가 확인이다 — 붙지 못하면 마이그레이션이 돌 수 없다.
    """
    with _schema(engine, "url_probe"):
        command.upgrade(_config_for_schema(engine, "url_probe"), "head")


# ── 마이그레이션과 모델을 견준다 ────────────────────────────────────────────


def _columns(engine: Engine, schema: str) -> dict[tuple[str, str], tuple[object, ...]]:
    """그 스키마의 컬럼 전부 — 이름 · 자료형 · 널 허용 · 기본값 · 길이."""
    sql = text(
        "SELECT table_name, column_name, data_type, is_nullable,"
        "       column_default, character_maximum_length, numeric_precision"
        "  FROM information_schema.columns"
        " WHERE table_schema = :schema"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"schema": schema}).all()

    def _normalise(value: object) -> object:
        # 기본값에 시퀀스 이름이 스키마째 들어간다 — 비교할 것은 구조다.
        if isinstance(value, str):
            return value.replace(f"{schema}.", "")
        return value

    return {(row[0], row[1]): tuple(_normalise(value) for value in row[2:]) for row in rows}


def _constraints(engine: Engine, schema: str) -> dict[tuple[str, str], str]:
    """그 스키마의 제약 전부 — 기본키 · 외래키 · 유일키 · CHECK 의 **정의까지**.

    `pg_get_constraintdef` 는 데이터베이스가 실제로 강제하는 식을 돌려준다.
    모델이 무엇을 적었는지가 아니라 **무엇이 걸렸는지**를 견주는 것이 요점이다.
    """
    sql = text(
        "SELECT c.relname, con.conname, pg_get_constraintdef(con.oid)"
        "  FROM pg_constraint con"
        "  JOIN pg_class c ON c.oid = con.conrelid"
        "  JOIN pg_namespace n ON n.oid = c.relnamespace"
        " WHERE n.nspname = :schema"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"schema": schema}).all()
    # 외래키 정의에 스키마 이름이 섞이므로 지운다 — 비교할 것은 구조다.
    return {
        (row[0], row[1]): row[2].replace(f"{schema}.", "")
        for row in rows
        if row[0] != "alembic_version"
    }


def _indexes(engine: Engine, schema: str) -> dict[tuple[str, str], str]:
    """그 스키마의 인덱스 전부 — **제약이 만들지 않은 것까지.**

    `pg_constraint` 는 기본키와 유일키가 만든 인덱스만 안다. `index=True` 로
    붙인 일반 인덱스는 거기 없으므로, 컬럼과 제약이 같아도 인덱스가 다른 두
    스키마가 통과할 수 있다.
    """
    sql = text(
        "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = :schema"
    )
    with engine.connect() as conn:
        rows = conn.execute(sql, {"schema": schema}).all()
    return {
        (str(row[0]), str(row[1])): str(row[2]).replace(f"{schema}.", "")
        for row in rows
        if row[0] != "alembic_version"
    }


@contextmanager
def _schema(engine: Engine, name: str) -> Iterator[None]:
    """빈 스키마 하나를 만들고 쓰고 지운다."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    try:
        yield
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _engine_for_schema(engine: Engine, schema: str) -> Engine:
    """그 스키마만 보는 엔진."""
    return create_engine(
        engine.url,
        connect_args={"options": f"-csearch_path={schema}"},
        poolclass=NullPool,
    )


def _config_for_schema(engine: Engine, schema: str) -> Config:
    url = engine.url.render_as_string(hide_password=False)
    joiner = "&" if "?" in url else "?"
    # `%` 를 두 번 적는 것은 프로덕션과 같은 함수에 맡긴다 — Alembic 설정은
    # configparser 이고, 거기서 `%` 는 보간 구문이라 한 번만 적으면 터진다.
    return _alembic_config(
        escaped_for_configparser(f"{url}{joiner}options=-csearch_path%3D{schema}")
    )


def test_the_migration_builds_the_same_tables_as_the_models(engine: Engine) -> None:
    """**마이그레이션으로 만든 표와 모델로 만든 표가 같아야 한다.**

    자동 생성이 CHECK 식을 문자열로 구워 박으므로 둘은 조용히 갈릴 수 있다 —
    모델을 고치고 리비전을 내지 않거나, 마이그레이션을 손으로 손보거나, 긴 식을
    읽기 좋게 줄바꿈하는 것만으로도. 갈린 쪽은 규칙을 잃고, 잃은 줄 아무도
    모른다.

    그래서 두 스키마를 실제로 만들어 **데이터베이스가 강제하는 정의**를
    견준다.
    """
    with _schema(engine, "from_migration"), _schema(engine, "from_models"):
        command.upgrade(_config_for_schema(engine, "from_migration"), "head")

        model_engine = _engine_for_schema(engine, "from_models")
        try:
            Base.metadata.create_all(model_engine)
        finally:
            model_engine.dispose()

        migrated_columns = _columns(engine, "from_migration")
        model_columns = _columns(engine, "from_models")
        # `alembic_version` 은 마이그레이션 쪽에만 있다 — 표가 아니라 기록이다.
        migrated_columns = {
            key: value for key, value in migrated_columns.items() if key[0] != "alembic_version"
        }

        assert migrated_columns == model_columns

        assert _constraints(engine, "from_migration") == _constraints(engine, "from_models")
        assert _indexes(engine, "from_migration") == _indexes(engine, "from_models")


def test_downgrade_takes_every_table_back_out(engine: Engine) -> None:
    """되돌리는 방법이 있어야 한다 — 그리고 실제로 돌아야 한다."""
    with _schema(engine, "round_trip"):
        config = _config_for_schema(engine, "round_trip")
        command.upgrade(config, "head")
        assert _columns(engine, "round_trip"), "올렸는데 표가 하나도 없다"

        command.downgrade(config, "base")

        remaining = {table for table, _ in _columns(engine, "round_trip")}
        assert remaining <= {"alembic_version"}, f"내렸는데 남은 표가 있다: {remaining}"


def test_a_percent_in_the_url_does_not_break_alembic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**비밀번호에 `@` 가 하나만 있어도 URL 인코딩이 `%40` 을 만든다.**

    Alembic 설정은 configparser 이고 거기서 `%` 는 보간 구문이라, 그대로 넣으면
    데이터베이스에 붙어 보기도 전에 터진다. 흔한 비밀번호 하나가 마이그레이션을
    통째로 막는 자리였다.

    **`env.py` 가 부르는 함수를 그대로 부른다.** 앞서 이 테스트는 이스케이프를
    자기가 다시 적어 견주고 있었다 — 그러면 프로덕션에서 이스케이프를 지워도
    테스트는 초록으로 남는다. 지키는 척만 하는 테스트다.
    """
    monkeypatch.setenv("ERP_DATABASE_URL", "postgresql+psycopg://erp:p%40ss@nowhere/erp")

    probe = Config(str(BACKEND_ROOT / "alembic.ini"))
    apply_database_url(probe)

    # 넣을 때 두 번 적은 `%` 가 읽을 때 한 번으로 돌아온다 — 설정에 붙어 보기도
    # 전에 터지지 않고, 붙을 때는 원래의 비밀번호가 나온다.
    assert probe.get_main_option("sqlalchemy.url") == get_settings().database_url


def test_the_url_the_caller_gives_is_not_escaped_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """부르는 쪽이 이미 넣어 둔 URL 을 **건드리지 않는다.**

    테스트와 `docker-entrypoint.sh` 가 URL 을 직접 주는 길이며, 여기서 한 번 더
    이스케이프하면 그 URL 이 조용히 달라진다.
    """
    monkeypatch.setenv("ERP_DATABASE_URL", "postgresql+psycopg://erp:p%40ss@nowhere/erp")

    given = "postgresql+psycopg://caller:caller@127.0.0.1:5432/erp_test"
    probe = Config(str(BACKEND_ROOT / "alembic.ini"))
    probe.set_main_option("sqlalchemy.url", given)
    apply_database_url(probe)

    assert probe.get_main_option("sqlalchemy.url") == given
