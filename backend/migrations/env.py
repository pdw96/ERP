"""Alembic 실행 환경.

URL 을 `alembic.ini` 에 적지 않고 여기서 설정에서 읽는다 — 두 벌을 두지
않기 위해서다.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

import app.db  # noqa: F401  — 모델 모듈을 불러들여 Base.metadata 를 채운다
from app.core import locks
from app.core.alembic_url import apply_database_url
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 부르는 쪽이 준 URL 과 설정값 중 어느 것이 이기는가, 퍼센트를 어떻게 적는가 —
# 둘 다 `app.core.alembic_url` 이 정한다. **테스트가 그 함수를 그대로 부른다.**
# 여기에 다시 적으면 테스트가 지키는 코드와 실제로 도는 코드가 갈린다.
apply_database_url(config)

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
            # **컨테이너 둘이 동시에 뜨면 같은 DDL 을 나란히 돌린다.** 둘 다 아직
            # 적용되지 않은 리비전을 보고 각자 `CREATE TABLE` 을 내고, 진 쪽은
            # `pg_type_typname_nsp_index` 유일 위반으로 **기동에 실패한다.**
            # 실제로 셋을 동시에 띄워 둘이 그렇게 죽는 것을 확인했다.
            #
            # 시드 구간에만 잠금을 걸어 두는 것은 반쪽이다 — 시드에 닿기 전에
            # 여기서 죽기 때문이다. 트랜잭션 잠금이므로 커밋이나 롤백과 함께
            # 저절로 풀린다.
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": locks.MIGRATION}
            )
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
