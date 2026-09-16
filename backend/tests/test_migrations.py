"""마이그레이션이 모델과 같은 표를 만드는가.

자동 생성은 CHECK 식을 **실행 시점 방언으로 문자열로 구워 박는다.** 그래서
모델을 고치고 마이그레이션을 다시 내지 않으면, 또는 마이그레이션을 손으로
고치면, 둘이 조용히 갈린다. 갈린 쪽은 규칙을 잃는데 아무도 모른다.

그래서 **두 스키마를 실제로 만들어 견준다** — 하나는 마이그레이션으로, 하나는
모델로. 컬럼과 제약 정의가 한 글자라도 다르면 여기서 걸린다. 읽기 좋으라고
CHECK 식을 줄바꿈하는 것조차 이 테스트가 잡는다.
"""

import os
import subprocess
import sys
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

from app import seed as seed_module
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
    """그 스키마의 컬럼 전부 — 이름 · 자료형 · 널 허용 · 기본값 · 길이.

    **칸 순서는 견주지 않는다.** `ordinal_position` 을 뽑지 않으므로 두 길의
    칸 차례가 달라도 여기서는 같다고 나온다 — 마이그레이션의 `add_column` 은
    끝에 붙이고 모델은 선언한 자리에 두기 때문에 실제로 다르다.

    **그것을 허용한다.** 맞추려면 칸을 더할 때마다 표를 다시 만드는 리비전이
    필요한데, 얻는 것이 없다. 시드와 마이그레이션의 `INSERT` 는 전부 칸 이름을
    적고 `SELECT *` 의 순서에 기대는 코드가 없다. 이 테스트를 「두 스키마가
    완전히 같다」로 읽지 않기 위해 적어 둔다.
    """
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


def test_two_containers_can_migrate_at_the_same_time(engine: Engine) -> None:
    """**동시에 뜬 컨테이너가 서로를 죽이지 않는가.**

    compose 가 백엔드를 둘 이상 띄우면 각자 `alembic upgrade head` 로 시작한다.
    둘 다 아직 적용되지 않은 리비전을 보고 각자 `CREATE TABLE` 을 내면, 진 쪽은
    `pg_type_typname_nsp_index` 유일 위반으로 **기동에 실패한다.** 잠금을 걸기
    전에 넷을 동시에 띄워 둘이 실제로 그렇게 죽었다.

    시드 구간에만 잠금을 두는 것은 반쪽이다 — 시드에 닿기 전에 여기서 죽는다.

    **프로세스로 띄운다.** `alembic.context` 가 프로세스 전역이라 한 프로세스
    안의 스레드 둘로는 alembic 자신이 먼저 깨진다 — 재현되는 것은 우리 결함이
    아니라 그 전역이다. 기동은 원래 프로세스마다 일어난다.
    """
    schema = "concurrent_start"
    url = engine.url.render_as_string(hide_password=False)
    joiner = "&" if "?" in url else "?"
    # 퍼센트를 여기서 두 번 적지 않는다 — `env.py` 가 부르는 함수가 그 일을 한다.
    environment = {
        **os.environ,
        "ERP_DATABASE_URL": f"{url}{joiner}options=-csearch_path%3D{schema}",
    }

    with _schema(engine, schema):
        starters = [
            subprocess.Popen(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for _ in range(3)
        ]
        results = [
            (starter.wait(timeout=180), starter.communicate()[0]) for starter in starters
        ]

        died = [output for code, output in results if code != 0]
        assert not died, "동시에 마이그레이션하면 죽는다:\n" + "\n".join(died)
        assert {table for table, _ in _columns(engine, schema)} >= {"items", "lots"}


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


# ── 데이터 단계 — 이미 심긴 데이터베이스에서만 도는 길 ──────────────────────
#
# 위의 대조 테스트는 **빈 스키마**에 올린다. 그래서 자재군 리비전의 데이터
# 단계(`WHERE EXISTS (SELECT 1 FROM items)`)는 통째로 건너뛰어진다 — 저장소에서
# 처음으로 **데이터를 옮기는** 마이그레이션인데 그 부분만 아무 검사도 받지 않는
# 자리였다. 아래 둘이 그 자리를 덮는다.

_BEFORE_MATERIAL_GROUP = """
INSERT INTO code_groups (group_code, name, value_fixed, description) VALUES
  ('PROCESS', '공정', FALSE, '시험'),
  ('UOM', '단위', FALSE, '시험'),
  ('INSP_ITEM', '검사항목', FALSE, '시험');

INSERT INTO common_codes (group_code, code, name) VALUES
  ('PROCESS', '수입', '수입'),
  ('UOM', 'KG', '킬로그램'), ('UOM', 'L', '리터'), ('UOM', 'M2', '제곱미터'),
  ('INSP_ITEM', '입도', '입도'), ('INSP_ITEM', '수분', '수분'),
  ('INSP_ITEM', '점도', '점도'), ('INSP_ITEM', '두께', '두께'),
  ('INSP_ITEM', '색차', '색차'), ('INSP_ITEM', '이물', '이물'),
  ('INSP_ITEM', '포장', '포장'), ('INSP_ITEM', '성적서', '성적서');

INSERT INTO items
  (code, name, item_type, process, process_group, stock_uom, stock_uom_group,
   phase, safety_stock)
VALUES
  ('RM-01','폴리머 베이스','원자재','수입','PROCESS','KG','UOM','양산',800),
  ('RM-02','세라믹 분말','원자재','수입','PROCESS','KG','UOM','양산',400),
  ('RM-03','광학 안료','원자재','수입','PROCESS','KG','UOM','양산',150),
  ('RM-04','보강 섬유','원자재','수입','PROCESS','M2','UOM','양산',600),
  ('RM-05','접착 수지','원자재','수입','PROCESS','KG','UOM','양산',250),
  ('RM-06','방열 첨가제','원자재','수입','PROCESS','KG','UOM','양산',200),
  ('RM-07','차단 필름','원자재','수입','PROCESS','M2','UOM','양산',500),
  ('RM-08','표면 코팅제','원자재','수입','PROCESS','L','UOM','양산',300),
  ('RM-09','미세 충전재','원자재','수입','PROCESS','KG','UOM','양산',350),
  ('RM-10','유연 가소제','원자재','수입','PROCESS','L','UOM','양산',280),
  ('RM-11','보호 라이너','원자재','수입','PROCESS','M2','UOM','양산',450),
  ('RM-12','안정화 첨가제','원자재','수입','PROCESS','KG','UOM','양산',180),
  ('RM-13','전도성 페이스트','원자재','수입','PROCESS','KG','UOM','양산',120),
  ('RM-14','기능성 염료','원자재','수입','PROCESS','KG','UOM','양산',100),
  ('RM-15','포장 라미네이트','원자재','수입','PROCESS','M2','UOM','양산',700);

INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code, upper_spec_limit, lower_spec_limit,
   center_line, unit)
VALUES
  ('PROCESS','수입','INSP_ITEM','입도',   50.0,   10.0,   30.0, 'µm'),
  ('PROCESS','수입','INSP_ITEM','수분',    0.50,  NULL,    0.20, '%'),
  ('PROCESS','수입','INSP_ITEM','점도', 4000.0, 2000.0, 3000.0, 'cP'),
  ('PROCESS','수입','INSP_ITEM','두께',  105.0,   95.0,  100.0, 'µm'),
  ('PROCESS','수입','INSP_ITEM','색차',    1.00,  NULL,    0.30, 'ΔE'),
  ('PROCESS','수입','INSP_ITEM','이물',   NULL,   NULL,   NULL, NULL),
  ('PROCESS','수입','INSP_ITEM','포장',   NULL,   NULL,   NULL, NULL),
  ('PROCESS','수입','INSP_ITEM','성적서', NULL,   NULL,   NULL, NULL);
"""


def _material_groups(engine: Engine) -> dict[str, str]:
    """품목 코드마다 어느 무리인가."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT code, material_group FROM items WHERE material_group IS NOT NULL")
        ).all()
    return {str(row[0]): str(row[1]) for row in rows}


def _incoming_standards(engine: Engine) -> set[tuple[str, str]]:
    """수입 기준이 (검사항목, 자재군) 으로 어떻게 서 있는가."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT item_code, material_group FROM process_inspection_standards"
                " WHERE process_code = '수입'"
            )
        ).all()
    return {(str(row[0]), str(row[1])) for row in rows}


def _upgrade_over_the_old_seed(engine: Engine, schema: str) -> Engine:
    """옛 리비전까지 올리고 **옛 모양으로 심은 뒤** `head` 로 올린다."""
    config = _config_for_schema(engine, schema)
    command.upgrade(config, "3c602ffaebc3")

    scoped = _engine_for_schema(engine, schema)
    with scoped.begin() as conn:
        for statement in _BEFORE_MATERIAL_GROUP.strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))

    command.upgrade(config, "head")
    return scoped


def test_both_roads_reach_the_same_material_groups(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**두 길이 같은 곳에 닿는다.**

    자재군 배정은 마이그레이션(`_ITEM_GROUPS` · `_FIRST_GROUP`)과 시드
    SQL(`03_items.sql` · `05_quality.sql`) **양쪽에 적혀 있다.** 목록이 두 벌이면
    반드시 갈리므로, 갈리는 순간을 여기서 잡는다 — 한쪽만 고치면 빈 데이터베이스와
    이미 심긴 데이터베이스가 서로 다른 기준을 갖게 되고, 갈린 줄 아무도 모른다.

    견주는 것은 **값이 아니라 배정**이다. 규격 숫자는 옛 줄에서 따라오므로
    두 길이 같을 이유가 없고, 갈려서 문제가 되는 것은 어느 자재가 어느 무리인가다.
    """
    monkeypatch.setenv("ERP_SEED_ENABLED", "true")
    with _schema(engine, "road_seed"), _schema(engine, "road_migration"):
        # 길 A — 빈 데이터베이스에 올리고 시드가 채운다.
        command.upgrade(_config_for_schema(engine, "road_seed"), "head")
        seeded = _engine_for_schema(engine, "road_seed")
        assert seed_module.seed(seeded), "시드가 돌지 않았다"

        # 길 B — 옛 모양으로 심긴 데이터베이스를 마이그레이션이 옮긴다.
        migrated = _upgrade_over_the_old_seed(engine, "road_migration")

        assert _material_groups(migrated) == _material_groups(seeded)
        assert _incoming_standards(migrated) == _incoming_standards(seeded)


def test_the_data_step_moves_the_old_rows_instead_of_replacing_them(engine: Engine) -> None:
    """**사람이 고친 값이 마이그레이션을 건너간다.**

    이 리비전이 존재하는 근거가 「사람이 고친 값을 재시드가 덮어쓰는 쪽이 더 큰
    사고다」인데, 지우고 다시 심으면 그 재시드와 같은 일을 하게 된다. 옛 줄을
    옮겨 쓰는지 여기서 지킨다.

    **σ 는 따라가지 않는다** — 규격은 고객이 정하는 것이라 같은 항목이면 무리가
    달라도 쓸 수 있지만, σ 는 잰 값이고 새 무리에서는 잰 적이 없다.
    """
    with _schema(engine, "kept_values"):
        config = _config_for_schema(engine, "kept_values")
        command.upgrade(config, "3c602ffaebc3")

        scoped = _engine_for_schema(engine, "kept_values")
        with scoped.begin() as conn:
            for statement in _BEFORE_MATERIAL_GROUP.strip().split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            # 사람이 고친 값 — 실측 σ 와 좁힌 규격.
            conn.execute(
                text(
                    "UPDATE process_inspection_standards"
                    "   SET sigma = 0.05, sigma_source = '실측', upper_spec_limit = 0.40"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                )
            )

        command.upgrade(config, "head")

        with scoped.connect() as conn:
            kept = conn.execute(
                text(
                    "SELECT sigma, sigma_source, upper_spec_limit"
                    "  FROM process_inspection_standards"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                    "   AND material_group = '분체'"
                )
            ).one()
            copied = conn.execute(
                text(
                    "SELECT sigma, sigma_source, upper_spec_limit"
                    "  FROM process_inspection_standards"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                    "   AND material_group = '액상수지'"
                )
            ).one()

        # 옮겨 쓴 줄은 사람이 고친 값을 그대로 들고 있다.
        assert (kept[0], kept[1], kept[2]) == (0.05, "실측", 0.40)
        # 베낀 줄은 규격만 따라오고 σ 는 「미정」이다 — 그 무리에서는 잰 적이 없다.
        assert (copied[0], copied[1], copied[2]) == (None, "미정", 0.40)


def test_downgrade_keeps_the_values_it_moved(engine: Engine) -> None:
    """되돌려도 사람이 고친 값이 남는다 — 베낀 줄만 지운다."""
    with _schema(engine, "down_values"):
        config = _config_for_schema(engine, "down_values")
        command.upgrade(config, "3c602ffaebc3")

        scoped = _engine_for_schema(engine, "down_values")
        with scoped.begin() as conn:
            for statement in _BEFORE_MATERIAL_GROUP.strip().split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.execute(
                text(
                    "UPDATE process_inspection_standards SET upper_spec_limit = 0.40"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                )
            )

        command.upgrade(config, "head")
        command.downgrade(config, "3c602ffaebc3")

        with scoped.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT item_code, upper_spec_limit FROM process_inspection_standards"
                    " WHERE process_code = '수입' ORDER BY item_code"
                )
            ).all()

        assert len(rows) == 8, "되돌린 뒤에도 항목마다 한 줄이어야 한다"
        assert dict(rows)["수분"] == 0.40, "사람이 고친 규격이 되돌리기에서 사라졌다"


def test_a_raw_material_the_revision_does_not_know_stops_it(engine: Engine) -> None:
    """**모르는 원자재가 있으면 무엇이 남았는지 말하고 멈춘다.**

    그냥 두면 바로 뒤의 양방향 CHECK 가 대신 터지는데, 그 오류는 「제약 위반」일
    뿐이라 원인이 리비전의 목록에 있다는 것을 말해 주지 않는다. 트랜잭션 하나라
    멈추면 아무것도 남지 않는다 — **조용히 틀린 값이 들어가지 않는다.**
    """
    with _schema(engine, "unknown_material"):
        config = _config_for_schema(engine, "unknown_material")
        command.upgrade(config, "3c602ffaebc3")

        scoped = _engine_for_schema(engine, "unknown_material")
        with scoped.begin() as conn:
            for statement in _BEFORE_MATERIAL_GROUP.strip().split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.execute(
                text(
                    "INSERT INTO items"
                    " (code, name, item_type, process, process_group, stock_uom,"
                    "  stock_uom_group, phase, safety_stock)"
                    " VALUES ('RM-99','새 자재','원자재','수입','PROCESS','KG','UOM','양산',10)"
                )
            )

        with pytest.raises(Exception, match="RM-99"):
            command.upgrade(config, "head")
