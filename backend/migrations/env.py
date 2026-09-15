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
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

# `app.db` 를 위에서 불러들였으므로 metadata 가 표를 전부 알고 있다.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 에 붙지 않고 SQL 만 뽑는다."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # CHECK 제약을 이름으로 비교할 수 있어야 마이그레이션과 모델을 견줄 수 있다.
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
