"""시드 — 조각 7b.

세 조건과 **트랜잭션 하나**를 본다. 그리고 심긴 기준정보가 스스로 정합한지 —
쓰이지 않는 코드나 가리킬 곳 없는 참조가 없는지 — 를 본다.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app import seed as seed_module
from app.core import codes
from app.db.base import Base

SCHEMA = "seed_probe"


@pytest.fixture
def blank(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """표만 선 빈 스키마. 스위치는 켜 둔다."""
    monkeypatch.setenv("ERP_SEED_ENABLED", "true")
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{SCHEMA}"'))

    scoped = create_engine(
        engine.url,
        connect_args={"options": f"-csearch_path={SCHEMA}"},
        poolclass=NullPool,
    )
    Base.metadata.create_all(scoped)
    try:
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))


def _count(engine: Engine, table: str, where: str = "") -> int:
    clause = f" WHERE {where}" if where else ""
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT count(*) FROM {table}{clause}")).scalar_one())


# ── 세 조건 ─────────────────────────────────────────────────────────────────


def test_nothing_is_planted_while_the_switch_is_off(
    blank: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """운영에서 자동 시드는 사고이지 편의가 아니다."""
    monkeypatch.setenv("ERP_SEED_ENABLED", "false")

    assert seed_module.seed(blank) is False
    assert _count(blank, "items") == 0


def test_the_seed_plants_into_an_empty_database(blank: Engine) -> None:
    """세 조건을 다 통과하면 심는다."""
    assert seed_module.seed(blank) is True
    assert _count(blank, "items") == 25


def test_a_second_run_changes_nothing(blank: Engine) -> None:
    """**물어야 할 것은 표의 유무가 아니라 내용의 유무다.**

    마이그레이션이 표를 항상 만들어 두므로 「표가 있는가」는 아무것도 말해 주지
    않는다. 재기동해도 두 번 심지 않는다.
    """
    assert seed_module.seed(blank) is True
    before = _count(blank, "common_codes")

    assert seed_module.seed(blank) is False
    assert _count(blank, "common_codes") == before


def test_a_failure_halfway_leaves_nothing_behind(
    blank: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """**「반쯤 채워짐」이라는 상태를 없앤다.**

    PostgreSQL 에는 지우고 다시 시작할 파일이 없다. 반쯤 채워진 데이터베이스는
    「비어 있지 않다」로 판정되어 다시는 시드되지 않고 고장난 채로 굳는다.
    """
    import pathlib

    fake = pathlib.Path(str(tmp_path))
    (fake / "01_ok.sql").write_text(
        "INSERT INTO code_groups (group_code, name, value_fixed, description)"
        " VALUES ('WAREHOUSE', '창고', TRUE, '');",
        encoding="utf-8",
    )
    (fake / "02_broken.sql").write_text("INSERT INTO 없는표 VALUES (1);", encoding="utf-8")
    monkeypatch.setattr(seed_module, "SEED_DIR", fake)

    with pytest.raises(Exception, match="없는표|does not exist"):
        seed_module.seed(blank)

    assert _count(blank, "code_groups") == 0, "터진 시드가 앞 파일의 줄을 남겼다"


# ── 심긴 것이 스스로 정합한가 ───────────────────────────────────────────────


def test_the_groups_in_the_database_match_the_ones_the_program_calls(
    blank: Engine,
) -> None:
    """**목록을 두 벌 두면 반드시 갈린다.**

    프로그램은 그룹을 이름으로 부른다. 데이터베이스에 없는 그룹을 부르면 코드가
    터지고, 아무도 안 부르는 그룹이 남으면 화면에 쓰이지 않는 트리가 뜬다.
    """
    seed_module.seed(blank)

    with blank.connect() as conn:
        planted = {row[0] for row in conn.execute(text("SELECT group_code FROM code_groups"))}

    assert planted == set(codes.GROUP_CODES)


def test_every_measured_reason_points_at_an_item_that_exists(blank: Engine) -> None:
    """계량 코드는 검사 항목의 판정 결과일 뿐이다 — 가리킬 항목이 있어야 한다."""
    seed_module.seed(blank)

    assert _count(blank, "nonconformity_attributes", "measure_kind = '계량'") == 14
    assert (
        _count(
            blank,
            "nonconformity_attributes",
            "measure_kind = '계량' AND inspection_item_code IS NULL",
        )
        == 0
    )


def test_no_raw_material_sits_outside_the_bom(blank: Engine) -> None:
    """**쓰이지 않는 자재는 소요량 계산에 나오지 않는다.**

    기준정보에 있는데 어느 반제품에도 안 들어가면 그 품목은 발주될 이유가 없다.
    시드가 그런 줄을 남기면 화면에서는 있는 것처럼 보인다.
    """
    seed_module.seed(blank)

    orphans = _count(
        blank,
        "items",
        "item_type = '원자재' AND id NOT IN (SELECT child_item_id FROM bom_components)",
    )
    assert orphans == 0


def test_the_bom_actually_goes_two_levels_deep(blank: Engine) -> None:
    """반제품이 가운데 서는지 본다 — 이것이 품목 통합이 산 것이다."""
    seed_module.seed(blank)

    with blank.connect() as conn:
        chains = conn.execute(
            text(
                "SELECT count(*) FROM bom_components top"
                "  JOIN bom_components sub ON sub.parent_item_id = top.child_item_id"
                " WHERE top.level = 1 AND sub.level = 2"
            )
        ).scalar_one()

    assert chains == 19, "완제품 → 반제품 → 원자재로 이어지는 사슬이 끊겼다"


def test_the_adjustment_reasons_are_deliberately_empty(blank: Engine) -> None:
    """**실제로 조정을 내 보아야 목록이 나온다.**

    비어 있는 것이 빠뜨린 것이 아니라 정한 것이다 — 빈 기준정보는 없는
    기준정보보다 나쁘지만, 지어낸 기준정보는 그보다 나쁘다.
    """
    seed_module.seed(blank)

    assert _count(blank, "common_codes", "group_code = 'ADJ_REASON'") == 0


def test_every_sigma_is_left_undecided(blank: Engine) -> None:
    """규격에서 뽑은 σ 는 Cpk 를 계수의 역수로 못박는다 — 비워 두는 편이 안전하다."""
    seed_module.seed(blank)

    assert _count(blank, "process_inspection_standards", "sigma IS NOT NULL") == 0
    assert _count(blank, "process_inspection_standards", "sigma_source <> '미정'") == 0


def test_no_lot_is_planted(blank: Engine) -> None:
    """로트는 거래 표다 — **비어 있는 것이 정상 상태**다.

    로트가 생기는 것은 IQC 합격이고, 그것은 2단계의 일이다.
    """
    seed_module.seed(blank)

    assert _count(blank, "lots") == 0


def test_the_same_reason_disposes_differently_by_stage_in_the_seed(blank: Engine) -> None:
    """처분이 「코드 × 단계」에 붙는다는 것이 실제 데이터에서 드러난다."""
    seed_module.seed(blank)

    with blank.connect() as conn:
        rows = dict(
            conn.execute(
                text(
                    "SELECT stage_code, disposition FROM nonconformity_stage_rules"
                    " WHERE reason_code = 'FQ-THK'"
                )
            ).all()
        )

    assert rows["FQC"] == "재작업"
    assert rows["OQC"] == "등급 하향"
