"""마이그레이션이 모델과 같은 표를 만드는가.

자동 생성은 CHECK 식을 **실행 시점 방언으로 문자열로 구워 박는다.** 그래서
모델을 고치고 마이그레이션을 다시 내지 않으면, 또는 마이그레이션을 손으로
고치면, 둘이 조용히 갈린다. 갈린 쪽은 규칙을 잃는데 아무도 모른다.

그래서 **두 스키마를 실제로 만들어 견준다** — 하나는 마이그레이션으로, 하나는
모델로. 컬럼과 제약의 **뜻**이 다르면 여기서 걸린다.

**공백과 줄바꿈은 잡지 못한다.** `pg_get_constraintdef` 는 데이터베이스가 저장한
식을 정규화해 돌려주므로, CHECK 식 한가운데에 줄바꿈을 넣어도 비교 전에 사라진다
(`IN ('수입')` 이 `= '수입'::text` 로 다시 쓰이는 것까지 정규화된다). 이 테스트를
「두 스키마가 완전히 같다」로 읽지 않는다 — 잡는 것은 뜻이다.
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

    **정규화된 식이라 공백은 견주지 않는다.** PostgreSQL 이 줄바꿈과 여분의
    공백을 지우고 표현도 다시 쓰므로(`IN ('수입')` → `= '수입'::text`), 식을
    읽기 좋게 줄바꿈해도 이 비교는 통과한다. 잡는 것은 **뜻이 달라진 자리**다.
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
    모델을 고치고 리비전을 내지 않거나, 마이그레이션을 손으로 손보면서 **식의 뜻을
    바꾸거나.** 갈린 쪽은 규칙을 잃고, 잃은 줄 아무도 모른다.

    **줄바꿈만으로는 갈리지 않는다.** 예전에 여기 그렇게 적혀 있었으나 사실이
    아니다 — `pg_get_constraintdef` 가 정규화하므로 공백은 비교 전에 사라진다.
    위의 모듈 독스트링과 `_constraints()` 가 같은 것을 말한다.

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


def test_containers_starting_together_do_not_kill_each_other(engine: Engine) -> None:
    """**동시에 뜬 컨테이너가 서로를 죽이지 않는가.**

    compose 가 백엔드를 둘 이상 띄우면 각자 `alembic upgrade head` 로 시작한다.
    둘 다 아직 적용되지 않은 리비전을 보고 각자 `CREATE TABLE` 을 내면, 진 쪽은
    `pg_type_typname_nsp_index` 유일 위반으로 **기동에 실패한다.** 잠금을 걸기
    전에 넷을 동시에 띄웠을 때 둘이 실제로 그렇게 죽었다. 여기서는 셋을 띄운다 —
    이름에 수를 넣지 않는 것은 수가 코드보다 먼저 낡기 때문이다.

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
# 자리였다. 아래 절 전체가 그 자리를 덮는다.

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

-- **옛 시드와 같은 값이어야 한다.** 이 픽스처는 「옛 DB」를 재현한다고 이름 붙어
-- 있으므로 한 칸이라도 다르면 한 번도 존재한 적 없는 상태 위에서 초록이 뜬다.
-- `time_variant` 는 만료 재검사가 보는 유일한 잣대라 특히 그렇다 — 처음에는 적지
-- 않아 여덟 줄이 전부 FALSE 로 섰고, 옛 시드는 수분 · 점도 · 색차 · 포장에 TRUE 다.
-- `warning_ratio` 와 `sigma_source` 는 server_default 와 같지만 함께 적어 둔다.
INSERT INTO process_inspection_standards
  (process_group, process_code, item_group, item_code, upper_spec_limit, lower_spec_limit,
   center_line, warning_ratio, sigma, sigma_source, time_variant, unit)
VALUES
  ('PROCESS','수입','INSP_ITEM','입도',50.0,10.0,30.0,0.70,NULL,'미정',FALSE,'µm'),
  ('PROCESS','수입','INSP_ITEM','수분',0.50,NULL,0.20,0.70,NULL,'미정',TRUE,'%'),
  ('PROCESS','수입','INSP_ITEM','점도',4000.0,2000.0,3000.0,0.70,NULL,'미정',TRUE,'cP'),
  ('PROCESS','수입','INSP_ITEM','두께',105.0,95.0,100.0,0.70,NULL,'미정',FALSE,'µm'),
  ('PROCESS','수입','INSP_ITEM','색차',1.00,NULL,0.30,0.70,NULL,'미정',TRUE,'ΔE'),
  ('PROCESS','수입','INSP_ITEM','이물',NULL,NULL,NULL,0.70,NULL,'미정',FALSE,NULL),
  ('PROCESS','수입','INSP_ITEM','포장',NULL,NULL,NULL,0.70,NULL,'미정',TRUE,NULL),
  ('PROCESS','수입','INSP_ITEM','성적서',NULL,NULL,NULL,0.70,NULL,'미정',FALSE,NULL);
"""


def _material_groups(engine: Engine) -> dict[str, str]:
    """품목 코드마다 어느 무리인가."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT code, material_group FROM items WHERE material_group IS NOT NULL")
        ).all()
    return {str(row[0]): str(row[1]) for row in rows}


def _incoming_standards(engine: Engine) -> set[tuple[object, ...]]:
    """수입 기준 한 줄 전부 — 배정과 **값까지**.

    배정만 견주면 픽스처가 옛 시드와 달라도 초록이 뜬다. 실제로 그랬다 —
    `_BEFORE_MATERIAL_GROUP` 이 `time_variant` 를 적지 않아 여덟 줄이 전부
    `FALSE` 로 섰는데 아무도 잡지 않았다. 만료 재검사가 보는 유일한 잣대라
    2단계에 그것이 들어오면 **한 번도 존재한 적 없는 상태 위에서 초록이 뜬다.**

    두 길의 값이 같아야 하는 이유는 마이그레이션이 옛 줄을 **옮기기** 때문이다 —
    지우고 다시 심지 않으므로 옛 시드의 값이 그대로 따라온다.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT item_code, material_group, upper_spec_limit, lower_spec_limit,"
                "       center_line, warning_ratio, sigma, sigma_source, time_variant, unit"
                "  FROM process_inspection_standards WHERE process_code = '수입'"
            )
        ).all()
    return {tuple(row) for row in rows}


def _material_group_codes(engine: Engine) -> set[tuple[object, ...]]:
    """자재군 그룹과 그 코드 셋 — **이름 · 정렬 · 설명까지.**

    코드가 **존재하는지**는 외래키가 지키지만 그 코드가 **무엇이라고 불리는지**는
    아무도 보지 않았다. 마이그레이션과 시드가 각각 적는 자리라, 한쪽만 고치면
    이미 심긴 DB 와 새로 심은 DB 가 같은 주소를 다른 이름으로 보여 준다.
    """
    with engine.connect() as conn:
        group = conn.execute(
            text(
                "SELECT name, value_fixed, description FROM code_groups"
                " WHERE group_code = 'MATERIAL_GROUP'"
            )
        ).all()
        codes = conn.execute(
            text(
                "SELECT code, name, sort_order, description, is_active FROM common_codes"
                " WHERE group_code = 'MATERIAL_GROUP'"
            )
        ).all()
    return {("그룹", *row) for row in group} | {("코드", *row) for row in codes}


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

    **배정과 값, 그리고 코드의 이름까지 견준다.** 마이그레이션이 옛 줄을 지우지 않고
    옮기므로 두 길의 값도 같아야 한다 — 그리고 그 덕에 「옛 DB」 픽스처가 진짜 옛 DB
    와 같은지도 여기서 지켜진다.

    자재군 코드의 **이름 · 정렬 · 설명**도 두 벌로 적혀 있다(마이그레이션과
    `01_common_codes.sql`). 코드가 있는지는 외래키가 지키지만 무엇이라 불리는지는
    아무도 보지 않아, 한쪽만 고치면 같은 주소가 두 이름을 갖는다.
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
        assert _material_group_codes(migrated) == _material_group_codes(seeded)


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
    """되돌려도 사람이 고친 값이 남는다.

    항목마다 남길 한 줄만 남고 나머지는 지워진다 — 「베낀 줄만」이 아니다. 남는
    줄이 옮겨 쓴 옛 줄이라 사람이 고친 값이 거기 있다.
    """
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


def _plant_old_shape(engine: Engine, schema: str, *, extra: str = "") -> tuple[Config, Engine]:
    """옛 리비전까지 올리고 옛 모양으로 심는다. `extra` 로 한 줄 더 얹는다."""
    config = _config_for_schema(engine, schema)
    command.upgrade(config, "3c602ffaebc3")
    scoped = _engine_for_schema(engine, schema)
    with scoped.begin() as conn:
        for statement in (_BEFORE_MATERIAL_GROUP + extra).strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))
    return config, scoped


def test_an_inspection_item_the_revision_does_not_know_stops_it(engine: Engine) -> None:
    """**모르는 수입 검사항목도 이름을 말하고 멈춘다.**

    원자재 경로에는 테스트가 있었지만 이 경로는 도달 가능한데 검사되지 않았다 —
    도달 못 하는 방어 코드가 아니라 **검사되지 않는** 방어 코드였다.
    """
    with _schema(engine, "unknown_item"):
        config, _ = _plant_old_shape(
            engine,
            "unknown_item",
            extra=(
                ";INSERT INTO common_codes (group_code, code, name)"
                " VALUES ('INSP_ITEM','밀도','밀도');"
                "INSERT INTO process_inspection_standards"
                " (process_group, process_code, item_group, item_code)"
                " VALUES ('PROCESS','수입','INSP_ITEM','밀도')"
            ),
        )

        with pytest.raises(Exception, match="밀도"):
            command.upgrade(config, "head")


def test_a_group_someone_already_made_does_not_stop_it(engine: Engine) -> None:
    """**자재군 그룹이 이미 있어도 올라간다.**

    자재군은 「값이 늘 수 있는 그룹」이라 운영자가 먼저 만들어 두었을 수 있다.
    그대로 `INSERT` 하면 「제약 위반」만 보이고 원인이 이 리비전에 있다는 것을
    말해 주지 않았다.
    """
    with _schema(engine, "group_exists"):
        config, scoped = _plant_old_shape(
            engine,
            "group_exists",
            extra=(
                ";INSERT INTO code_groups (group_code, name, value_fixed, description)"
                " VALUES ('MATERIAL_GROUP','자재군',FALSE,'운영자가 먼저 만들었다');"
                "INSERT INTO common_codes (group_code, code, name)"
                " VALUES ('MATERIAL_GROUP','분체','분체')"
            ),
        )

        command.upgrade(config, "head")

        with scoped.connect() as conn:
            planted = conn.execute(
                text("SELECT count(*) FROM common_codes WHERE group_code = 'MATERIAL_GROUP'")
            ).scalar_one()
        assert planted == 3, "먼저 있던 코드를 두고 나머지만 채워야 한다"


def test_a_group_that_means_something_else_stops_it(engine: Engine) -> None:
    """뜻이 다른 그룹이면 넘어가지 않고 멈춘다 — `value_fixed` 가 참이면 화면에서
    무리를 못 늘리게 된다. 자재군과 정반대다."""
    with _schema(engine, "group_differs"):
        config, _ = _plant_old_shape(
            engine,
            "group_differs",
            extra=(
                ";INSERT INTO code_groups (group_code, name, value_fixed, description)"
                " VALUES ('MATERIAL_GROUP','자재군',TRUE,'분기한다고 적힌 그룹')"
            ),
        )

        with pytest.raises(Exception, match="value_fixed"):
            command.upgrade(config, "head")


def test_downgrade_says_what_it_would_erase(engine: Engine) -> None:
    """**되돌리기가 남의 줄을 조용히 지우지 않는다.**

    옛 기본키가 항목마다 한 줄만 받으므로 줄이는 것 자체는 피할 수 없다. 피할 수
    있는 것은 **조용한 것**이다 — upgrade 는 멈출 때 이유를 말하는데 downgrade 는
    아무 말도 하지 않았다.
    """
    with _schema(engine, "down_speaks"):
        config, scoped = _plant_old_shape(engine, "down_speaks")
        command.upgrade(config, "head")

        # 운영자가 넷째 무리와 그 무리의 기준 한 줄을 더한다.
        with scoped.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO common_codes (group_code, code, name)"
                    " VALUES ('MATERIAL_GROUP','금속','금속')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO process_inspection_standards"
                    " (process_group, process_code, item_group, item_code, material_group)"
                    " VALUES ('PROCESS','수입','INSP_ITEM','두께','금속')"
                )
            )

        with pytest.raises(Exception, match="금속"):
            command.downgrade(config, "3c602ffaebc3")


def test_downgrade_says_when_a_measured_sigma_would_vanish(engine: Engine) -> None:
    """잰 값이 사라지는 것도 말하고 멈춘다 — 실측 σ 는 잰 사실이다."""
    with _schema(engine, "down_sigma"):
        config, scoped = _plant_old_shape(engine, "down_sigma")
        command.upgrade(config, "head")

        # 베낀 줄(수분/액상수지)에 실측 σ 를 채운다. 남는 줄은 수분/분체 쪽이다.
        with scoped.begin() as conn:
            conn.execute(
                text(
                    "UPDATE process_inspection_standards"
                    "   SET sigma = 0.11, sigma_source = '실측'"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                    "   AND material_group = '액상수지'"
                )
            )

        with pytest.raises(Exception, match="수분/액상수지"):
            command.downgrade(config, "3c602ffaebc3")


def test_downgrade_says_when_a_code_someone_else_made_would_vanish(engine: Engine) -> None:
    """**올릴 때 넘어간 남의 줄을 되돌릴 때 지우지 않는다.**

    「이미 있으면 넘어간다」를 넣으면서 운영자가 먼저 만든 줄이 살아서 upgrade 를
    건너오게 됐는데, downgrade 는 이름으로 셋을 지우므로 **심지 않은 것까지**
    지웠다 — 고침 하나가 한 표 옆에 같은 자리를 새로 연 것이다.
    """
    with _schema(engine, "down_others_code"):
        config, scoped = _plant_old_shape(
            engine,
            "down_others_code",
            extra=(
                ";INSERT INTO code_groups (group_code, name, value_fixed, description)"
                " VALUES ('MATERIAL_GROUP','자재군',FALSE,'수입 검사 기준이 걸리는 축이다.');"
                "INSERT INTO common_codes (group_code, code, name, sort_order, description)"
                " VALUES ('MATERIAL_GROUP','분체','운영자가 붙인 이름',1,'운영자가 적었다')"
            ),
        )
        command.upgrade(config, "head")

        # 올릴 때는 넘어간다 — 운영자의 이름이 그대로 남아 있어야 한다.
        with scoped.connect() as conn:
            kept = conn.execute(
                text(
                    "SELECT name FROM common_codes"
                    " WHERE group_code = 'MATERIAL_GROUP' AND code = '분체'"
                )
            ).scalar_one()
        assert kept == "운영자가 붙인 이름"

        # 되돌릴 때는 그것을 지우려 하므로 이름을 말하고 멈춘다.
        with pytest.raises(Exception, match="분체"):
            command.downgrade(config, "3c602ffaebc3")


def test_downgrade_says_when_someone_changed_an_item_group(engine: Engine) -> None:
    """**칸을 떨어뜨리는 것도 지우는 것이다.**

    멈춤 검사가 `DELETE` 세 자리만 보고 `drop_column("items","material_group")` 을
    지나쳤다. 사람이 `RM-12` 의 무리를 고쳐 두어도 되돌리기는 아무 말 없이 칸을
    가져갔고, 다시 올리면 `_ITEM_GROUPS` 의 값이 **사람의 판단을 덮었다.**

    하필 `RM-12` 는 대장이 「코드로 판정할 수 없다, 사람이 본다」로 적어 둔 품목이다
    — 사람이 보고 고칠 것을 전제한 칸인데 그 고침이 남지 않았다.
    """
    with _schema(engine, "down_item_group"):
        config, scoped = _plant_old_shape(engine, "down_item_group")
        command.upgrade(config, "head")

        with scoped.begin() as conn:
            conn.execute(
                text("UPDATE items SET material_group = '액상수지' WHERE code = 'RM-12'")
            )

        with pytest.raises(Exception, match="RM-12"):
            command.downgrade(config, "3c602ffaebc3")

        # 멈췄으면 사람이 고친 값이 그대로 있어야 한다 — 트랜잭션 하나이므로 롤백된다.
        assert _material_groups(scoped)["RM-12"] == "액상수지"


def test_downgrade_says_when_someone_added_a_raw_material(engine: Engine) -> None:
    """이 리비전이 **모르는** 원자재의 배정도 사라진다 — 고친 것과 같이 본다."""
    with _schema(engine, "down_new_item"):
        config, scoped = _plant_old_shape(engine, "down_new_item")
        command.upgrade(config, "head")

        with scoped.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO items (code, name, item_type, process, process_group,"
                    " stock_uom, stock_uom_group, phase, safety_stock,"
                    " material_group, material_group_group)"
                    " VALUES ('RM-16','운영자가 더한 자재','원자재','수입','PROCESS',"
                    " 'KG','UOM','양산',120,'분체','MATERIAL_GROUP')"
                )
            )

        with pytest.raises(Exception, match="RM-16"):
            command.downgrade(config, "3c602ffaebc3")


def test_downgrade_keeps_a_code_someone_else_made(engine: Engine) -> None:
    """**넷째 무리를 사람이 만들었으면 되돌린 뒤에도 남는다.**

    NC-8 이 고친 자리인데 탐침으로만 확인됐지 검사로 굳지 않았다. 그래서 지우는
    쪽의 목록에 `'금속'` 을 한 글자 더해도 — 즉 NC-8 을 그대로 되돌려도 — 아무
    테스트가 물지 않았다. 기존 테스트는 기준 줄 가드가 **먼저** 터져 코드 `DELETE`
    까지 닿지 않기 때문이다. 여기서는 코드만 더해 그 자리까지 실제로 내려간다.
    """
    with _schema(engine, "down_keeps_code"):
        config, scoped = _plant_old_shape(engine, "down_keeps_code")
        command.upgrade(config, "head")

        with scoped.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO common_codes (group_code, code, name, sort_order, description)"
                    " VALUES ('MATERIAL_GROUP','금속','금속',4,'운영자가 만들었다')"
                )
            )

        command.downgrade(config, "3c602ffaebc3")

        # 심은 셋은 사라지고 남의 것은 남는다. 그룹도 남는다 — 값이 남아 있으므로.
        with scoped.connect() as conn:
            left = (
                conn.execute(
                    text("SELECT code FROM common_codes WHERE group_code = 'MATERIAL_GROUP'")
                )
                .scalars()
                .all()
            )
            groups = (
                conn.execute(
                    text(
                        "SELECT group_code FROM code_groups WHERE group_code = 'MATERIAL_GROUP'"
                    )
                )
                .scalars()
                .all()
            )
        assert list(left) == ["금속"]
        assert list(groups) == ["MATERIAL_GROUP"]


def test_downgrade_says_when_an_arbitrary_sigma_would_vanish(engine: Engine) -> None:
    """**「임의」 σ 도 사람이 넣은 값이다.**

    조건을 `sigma_source = '실측'` 으로 되좁혀도 아무 테스트가 실패하지 않았다 —
    「임의」를 밟는 줄이 한 줄도 없었기 때문이다. 좁히면 운영자가 넣은 값이 다시
    조용히 사라진다. 말을 넓혔으면 그 넓힘을 지키는 것이 있어야 한다.
    """
    with _schema(engine, "down_sigma_arbitrary"):
        config, scoped = _plant_old_shape(engine, "down_sigma_arbitrary")
        command.upgrade(config, "head")

        with scoped.begin() as conn:
            conn.execute(
                text(
                    "UPDATE process_inspection_standards"
                    "   SET sigma = 0.09, sigma_source = '임의'"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                    "   AND material_group = '액상수지'"
                )
            )

        with pytest.raises(Exception, match="수분/액상수지"):
            command.downgrade(config, "3c602ffaebc3")


def test_downgrade_does_not_stop_for_a_sigma_on_the_row_it_keeps(engine: Engine) -> None:
    """**남길 줄의 σ 는 멈출 이유가 아니다** — 거짓 멈춤 갈래.

    위의 갈래들은 전부 「멈추는가」를 묻는다. 그래서 가드를 **넓히는** 쪽으로 틀려도
    아무것도 물지 않는다 — 넓힌 가드는 더 자주 멈출 뿐이고, 멈추는 것을 기다리는
    검사는 그것을 통과로 읽는다.

    넓힐 자리가 이미 열려 있다. 줄 대 줄 비교는 σ 와 σ출처를 빼는데, 리비전에 적힌
    근거가 **거짓이다**(NC-31) — 「두 줄이 그 칸에서 갈릴 수 없다」가 아니라 남길 줄에
    실측 σ 가 있으면 **늘 갈린다**(베낀 줄은 「미정」으로 선다). 그 문장을 믿고
    `_COMPARED_VALUE_COLUMNS` 에서 `startswith("sigma")` 를 떼면, 사람이 σ 를 잰
    데이터베이스는 그날부터 **영구히 되돌릴 수 없다.** 그런데도 이 갈래를 세우기
    전에는 검사가 하나도 물지 않았다.

    여기서 막는다. 남길 줄(수분/분체)에만 실측 σ 를 넣고 되돌리기가 **통과하는지**
    본다 — σ 가드는 남길 줄의 σ 를 허용하고, 줄 비교는 σ 를 보지 않기 때문이다.
    """
    with _schema(engine, "down_sigma_kept"):
        config, scoped = _plant_old_shape(engine, "down_sigma_kept")
        command.upgrade(config, "head")

        # 남길 줄은 첫 무리다(`_FIRST_GROUP`: 수분 → 분체). 베낀 줄은 수분/액상수지.
        with scoped.begin() as conn:
            conn.execute(
                text(
                    "UPDATE process_inspection_standards"
                    "   SET sigma = 0.04, sigma_source = '실측'"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                    "   AND material_group = '분체'"
                )
            )

        command.downgrade(config, "3c602ffaebc3")

        # 통과했고, 사람이 잰 값은 그대로 남아 있다.
        with scoped.connect() as conn:
            kept = conn.execute(
                text(
                    "SELECT sigma, sigma_source FROM process_inspection_standards"
                    " WHERE process_code = '수입' AND item_code = '수분'"
                )
            ).all()
        assert [tuple(row) for row in kept] == [(0.04, "실측")]


def test_downgrade_says_when_a_group_specific_spec_would_vanish(engine: Engine) -> None:
    """**σ 만이 아니라 그 줄의 값 전부를 본다.**

    가드가 σ 하나만 보던 시절, 사람이 무리별로 적어 둔 규격은 되돌리기에서 아무
    말 없이 사라졌다. 이 표는 `(공정 × 검사항목 × 자재군)` 유일키라 **무리마다
    다른 규격을 허용하도록 설계됐고**, 규격은 「고객이 정한다」(설계 원칙 5).

    같은 모양의 다섯 번째였다 — 앞의 넷은 「지우는 자리」를 좁게 셌고 이것은 그
    자리에서 **사라지는 사실**을 좁게 셌다.

    **갈래는 비교 목록과 같은 폭이다** — `_COMPARED_VALUE_COLUMNS` 여섯 칸을 전부
    밟는다. 고칠 때 넷만 밟아 `lower_spec_limit` 과 `center_line` 이 검사 밖에
    있었고, 그래서 비교에서 그 둘을 빼도 초록이 떴다 (NC-32).
    """
    for label, column, value in (
        ("usl", "upper_spec_limit", "0.31"),
        ("lsl", "lower_spec_limit", "0.05"),
        ("cl", "center_line", "0.30"),
        ("warn", "warning_ratio", "0.5"),
        ("tv", "time_variant", "NOT time_variant"),
        ("unit", "unit", "'ppm'"),
    ):
        with _schema(engine, f"down_spec_{label}"):
            config, scoped = _plant_old_shape(engine, f"down_spec_{label}")
            command.upgrade(config, "head")

            # 베낀 줄(수분/액상수지)에만 고친 값을 넣는다. 남는 줄은 수분/분체다.
            with scoped.begin() as conn:
                conn.execute(
                    text(
                        f"UPDATE process_inspection_standards SET {column} = {value}"
                        " WHERE process_code = '수입' AND item_code = '수분'"
                        "   AND material_group = '액상수지'"
                    )
                )

            with pytest.raises(Exception, match="수분/액상수지"):
                command.downgrade(config, "3c602ffaebc3")


def test_downgrade_says_when_the_group_someone_changed_would_vanish(engine: Engine) -> None:
    """**그룹 가드도 검사가 지킨다.**

    되돌리기 가드 다섯 중 이것 하나만 검사가 없었다 — 통째로 무력화해도 전부
    초록이었다. 죽은 코드가 아니라 **검사되지 않는** 코드였고, 「닫힌 부적합이
    검사 없이 닫혀 있으면 조용히 다시 열린다」가 NC-18 이 이미 낸 진단이다.

    **갈래는 가드와 같은 폭이다** — 가드가 견주는 `(name, value_fixed, description)`
    셋을 전부 밟는다. 처음에는 `value_fixed` 가 빠져 있었다 (NC-32).
    """
    for label, column, value in (
        ("name", "name", "'자재 무리'"),
        ("fixed", "value_fixed", "TRUE"),
        ("desc", "description", "'운영자가 고쳐 적었다'"),
    ):
        with _schema(engine, f"down_group_{label}"):
            config, scoped = _plant_old_shape(engine, f"down_group_{label}")
            command.upgrade(config, "head")

            with scoped.begin() as conn:
                conn.execute(
                    text(
                        f"UPDATE code_groups SET {column} = {value}"
                        " WHERE group_code = 'MATERIAL_GROUP'"
                    )
                )

            with pytest.raises(Exception, match="MATERIAL_GROUP"):
                command.downgrade(config, "3c602ffaebc3")


def test_the_guard_compares_more_than_the_name(engine: Engine) -> None:
    """가드는 이름만 보지 않는다 — **정렬 · 설명 · 활성까지** 본다.

    가드가 넷을 견주는데 테스트는 이름 하나만 어긋냈다. 그래서 비교에서 셋을 빼도
    초록이 떴다 — 가드의 **넓이**를 사람이 지키고 있었다는 뜻이다.
    """
    for label, column, value in (
        ("sort", "sort_order", "9"),
        ("desc", "description", "'운영자가 고쳐 적었다'"),
        ("active", "is_active", "FALSE"),
    ):
        with _schema(engine, f"guard_{label}"):
            config, scoped = _plant_old_shape(engine, f"guard_{label}")
            command.upgrade(config, "head")

            with scoped.begin() as conn:
                conn.execute(
                    text(
                        f"UPDATE common_codes SET {column} = {value}"
                        " WHERE group_code = 'MATERIAL_GROUP' AND code = '분체'"
                    )
                )

            with pytest.raises(Exception, match="분체"):
                command.downgrade(config, "3c602ffaebc3")


# ── 361ec789023c — 측정값 줄과 그 결속 ─────────────────────────────────────

# 검사 한 줄이 서는 데 필요한 최소 기준정보. **`inspections` 가 이미 선 모양**
# 이므로 자재군 칸은 아직 없다 — 그 칸을 붙이는 것이 시험 대상이다.
_BEFORE_MEASUREMENTS = """
INSERT INTO code_groups (group_code, name, value_fixed, description) VALUES
  ('PROCESS', '공정', FALSE, '시험'),
  ('UOM', '단위', FALSE, '시험'),
  ('MATERIAL_GROUP', '자재군', FALSE, '시험'),
  ('INSP_STAGE', '검사단계', TRUE, '시험');

INSERT INTO common_codes (group_code, code, name) VALUES
  ('PROCESS', '수입', '수입'),
  ('UOM', 'KG', '킬로그램'),
  ('MATERIAL_GROUP', '분체', '분체'),
  ('INSP_STAGE', 'IQC', '수입검사');

INSERT INTO items (code, name, item_type, process, process_group, material_group,
                   material_group_group, stock_uom, stock_uom_group, phase, safety_stock)
VALUES ('RM-01', '시험 원자재', '원자재', '수입', 'PROCESS', '분체',
        'MATERIAL_GROUP', 'KG', 'UOM', '양산', 100.0);

INSERT INTO partners (code, name, partner_type) VALUES ('SUP-01', '시험 공급사', '공급사');

INSERT INTO inspections (inspection_stage, stage_group, item_id, item_type,
                         supplier_id, supplier_type, supplier_lot_number, quantity,
                         judged_at, judged_by, result, nonconformity_group)
SELECT 'IQC', 'INSP_STAGE', i.id, i.item_type, p.id, p.partner_type,
       'SL-2026-0001', 500.0, TIMESTAMP '2026-09-21 09:00', '검사원 1', '합격', 'NC_REASON'
FROM items AS i, partners AS p WHERE i.code = 'RM-01' AND p.code = 'SUP-01';
"""


def test_the_data_step_fills_the_material_group_from_the_item(engine: Engine) -> None:
    """**이미 선 검사에 자재군이 채워진다 — 빈 DB 만 보면 이 단계는 한 번도 돌지 않는다.**

    리비전이 `inspections.material_group` 을 널 허용으로 붙이고, 품목에서 값을
    끌어와 채우고, 그 다음에 `NOT NULL` 로 조인다. 한 번에 `NOT NULL` 로 붙였다면
    **줄이 하나라도 있는 데이터베이스에서 그 자리가 터진다** — 그 차이는 검사 줄이
    실제로 있는 데이터베이스를 올려 보아야 드러난다.

    그리고 채우는 값은 **지어낸 것이 아니라 품목이 이미 아는 것**이어야 한다.
    """
    schema = "measurement_data_step"
    with _schema(engine, schema):
        config = _config_for_schema(engine, schema)
        command.upgrade(config, "992bb442d985")

        scoped = _engine_for_schema(engine, schema)
        with scoped.begin() as conn:
            for statement in _BEFORE_MEASUREMENTS.strip().split(";"):
                if statement.strip():
                    conn.execute(text(statement))

        command.upgrade(config, "head")

        with scoped.connect() as conn:
            filled = conn.execute(
                text(
                    "SELECT i.material_group, it.material_group"
                    " FROM inspections AS i JOIN items AS it ON it.id = i.item_id"
                )
            ).all()
            not_null = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns"
                    " WHERE table_schema = :schema AND table_name = 'inspections'"
                    " AND column_name = 'material_group'"
                ),
                {"schema": schema},
            ).scalar_one()

    assert filled == [("분체", "분체")], filled
    assert not_null == "NO"


# ── 08d406fa7f3b — 로트가 자기를 만든 검사를 가리킨다 ──────────────────────

# 검사 한 건과 그 검사가 만든 로트. **`inspections` 까지 선 모양**이므로 로트는
# 아직 검사를 모른다 — 그 칸을 붙이는 것이 시험 대상이다.
# **검사의 자재군 칸이 이미 선 모양**이라 `_BEFORE_MEASUREMENTS` 를 그대로 쓸 수
# 없다 — 그 절은 그 칸이 서기 **전**의 데이터베이스를 흉내 내는 것이다.
_BEFORE_WRITE_PATH = (
    _BEFORE_MEASUREMENTS.split("INSERT INTO inspections")[0]
    + """
INSERT INTO inspections (inspection_stage, stage_group, item_id, item_type, material_group,
                         supplier_id, supplier_type, supplier_lot_number, quantity,
                         judged_at, judged_by, result, nonconformity_group)
SELECT 'IQC', 'INSP_STAGE', i.id, i.item_type, i.material_group, p.id, p.partner_type,
       'SL-2026-0001', 500.0, TIMESTAMP '2026-09-21 09:00', '검사원 1', '합격', 'NC_REASON'
FROM items AS i, partners AS p WHERE i.code = 'RM-01' AND p.code = 'SUP-01';

INSERT INTO lots (item_id, item_type, lot_number, lot_origin, warehouse, stock_type,
                  quantity, received_date)
SELECT i.id, i.item_type, 'SL-2026-0001', '공급사', '원재료', '양품', 500.0, DATE '2026-09-21'
FROM items AS i WHERE i.code = 'RM-01';
"""
)


def _upgrade_with(engine: Engine, schema: str, revision: str, planted: str) -> Config:
    """그 리비전까지 올리고 **줄을 심는다.**"""
    config = _config_for_schema(engine, schema)
    command.upgrade(config, revision)
    scoped = _engine_for_schema(engine, schema)
    with scoped.begin() as conn:
        for statement in planted.strip().split(";"):
            if statement.strip():
                conn.execute(text(statement))
    return config


def test_upgrade_does_not_stop_for_a_lot_that_came_before(engine: Engine) -> None:
    """**제약이 사실을 막으면 안 된다.**

    「사 온 로트에는 검사가 있다」를 양방향으로 걸어 봤더니 **기초재고가
    막혔다** — 과거를 소급하지 않기로 했으므로 이월로 깔리는 자재 로트에는 적을
    검사가 없고, 그것은 이미 선 사실이다. 그래서 그 CHECK 를 빼고 **검사를
    가리키는 로트만** 판정에 묶는다.

    이 테스트가 그 되돌림을 지킨다 — 다시 걸면 여기서 빨개진다.
    """
    schema = "write_path_keeps_old_lots"
    with _schema(engine, schema):
        config = _upgrade_with(engine, schema, "e84fbec436c0", _BEFORE_WRITE_PATH)

        command.upgrade(config, "head")

        scoped = _engine_for_schema(engine, schema)
        with scoped.connect() as conn:
            kept = conn.execute(text("SELECT lot_number, inspection_id FROM lots")).all()

    assert kept == [("SL-2026-0001", None)], kept


def test_downgrade_says_which_lots_would_lose_their_judgement(engine: Engine) -> None:
    """**되돌리기가 사람이 남긴 것을 조용히 지우지 않는다.**

    칸 둘을 지우면 어느 판정이 그 로트를 만들었는지가 사라지고, 특채로 들어온
    로트는 표식까지 잃는다. 같은 모양이 이 저장소에서 여섯 번 나왔다 — 일곱
    번째로 만들지 않는다.
    """
    schema = "write_path_downgrade_guard"
    with _schema(engine, schema):
        config = _upgrade_with(engine, schema, "head", _BEFORE_WRITE_PATH)
        scoped = _engine_for_schema(engine, schema)
        with scoped.begin() as conn:
            conn.execute(
                text(
                    "UPDATE lots SET inspection_id = (SELECT id FROM inspections),"
                    " inspection_result = '합격', lot_number = '판정에서-나온-로트'"
                )
            )

        with pytest.raises(Exception, match="판정에서-나온-로트"):
            command.downgrade(config, "e84fbec436c0")


def test_downgrade_goes_quietly_when_no_lot_points_at_a_judgement(engine: Engine) -> None:
    """**가드가 정상 경로를 막지 않는다.**

    멈추는 것이 설계라면 멈추지 않아야 할 때 멈추지 않는 것도 설계다 — 가리키는
    로트가 하나도 없으면 조용히 내려간다.
    """
    schema = "write_path_downgrade_clean"
    with _schema(engine, schema):
        config = _upgrade_with(engine, schema, "head", _BEFORE_WRITE_PATH)

        command.downgrade(config, "e84fbec436c0")

        scoped = _engine_for_schema(engine, schema)
        with scoped.connect() as conn:
            columns = conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = :schema AND table_name = 'lots'"
                ),
                {"schema": schema},
            ).scalars()

    assert "inspection_id" not in set(columns)
