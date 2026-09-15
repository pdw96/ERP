"""Alembic 실행 환경.

URL 을 `alembic.ini` 에 적지 않고 여기서 설정에서 읽는다 — 두 벌을 두지
않기 위해서다.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.db  # noqa: F401  — 모델 모듈을 불러들여 Base.metadata 를 채운다
from app.core.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# **부르는 쪽이 URL 을 주면 그것이 이긴다.** 설정으로 무조건 덮으면 테스트가
# 자기 DB 를 가리켜도 앱의 기본 DB 로 붙고, 그 사고는 개발자의 로컬에 그
# 이름의 DB 가 있으면 **성공한 것처럼 보인다** — 실제로 그렇게 지나갔고 CI 가
# 잡았다. 설정은 아무도 주지 않았을 때의 기본값이지 우선값이 아니다.
if not config.get_main_option("sqlalchemy.url", None):
    # **퍼센트를 두 번 적는다.** Alembic 설정은 configparser 이고 거기서 `%` 는
    # 보간 구문이다. 비밀번호에 `@` 가 하나만 있어도 URL 인코딩이 `%40` 을
    # 만들고, 그대로 넣으면 붙어 보기도 전에 터진다.
    config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# `app.db` 를 위에서 불러들였으므로 metadata 가 표를 전부 알고 있다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 에 붙지 않고 SQL 만 뽑는다."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 컬럼 **타입** 변경을 autogenerate 가 감지하게 한다. CHECK 제약 비교와는
        # 무관하며, Alembic 은 CHECK 변경을 자동으로 감지하지 않는다 — 그쪽은
        # `tests/test_migrations.py` 가 두 스키마를 실제로 만들어 견준다.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """DB 에 붙어 실제로 돌린다."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
