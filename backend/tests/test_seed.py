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


def test_the_transaction_type_the_program_names_is_in_the_seed(blank: Engine) -> None:
    """**프로그램이 이름으로 부르는 수불유형이 시드에 있어야 한다.**

    수불유형 열둘의 값은 시드에만 있고 `codes.py` 에는 **부르는 쪽이 있는 하나만**
    적혀 있다(`TXN_PURCHASE_RECEIPT`). 한 벌 반이라 갈릴 수 있는 자리이므로 —
    시드에서 그 줄의 이름을 바꾸면 원장의 CHECK 가 아무 줄도 받지 않게 되고,
    그것은 **아무도 터지지 않는 고장**이다 — 여기서 둘을 견준다.

    **속성 줄까지 본다.** 코드만 있고 속성이 없으면 원장이 가리킬 수 없다.
    """
    seed_module.seed(blank)

    with blank.connect() as conn:
        planted = conn.execute(
            text(
                "SELECT a.total_effect FROM txn_type_attributes AS a"
                " JOIN common_codes AS c"
                " ON c.group_code = a.group_code AND c.code = a.code"
                " WHERE a.code = :code"
            ),
            {"code": codes.TXN_PURCHASE_RECEIPT},
        ).all()

    assert planted == [(codes.EFFECT_INCREASE,)], planted


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


def test_every_pair_in_the_seed_points_back(blank: Engine) -> None:
    """**짝은 서로를 가리켜야 한다.**

    제약은 여기까지 보지 못한다 — 같은 표의 다른 줄을 보는 조건은 CHECK 로
    적을 수 없어서, 외래키는 「짝으로 적은 줄이 있다」까지만 증명한다. A 가 B 를
    적고 B 가 C 를 적어도 두 줄 다 통과한다.

    그러면 창고를 건너는 이동에서 **한쪽만 나는 줄**이 선다: 나간 창고에서
    빠지는 줄이 없거나, 들어온 창고에 더해지는 줄이 없다. 어느 쪽이든 원장은
    맞는 것처럼 보이고 재고만 틀린다.

    지금 쓰기 경로는 시드뿐이므로 여기서 지킨다. 화면에서 코드를 만드는 길이
    생기는 날 쓰기 시점 검증이 함께 서야 한다 — `app/db/code_attributes.py` 가
    그렇게 적어 두었고, 이 테스트가 그 약속의 지금 몫이다.
    """
    seed_module.seed(blank)

    with blank.connect() as conn:
        pairs = dict(
            conn.execute(
                text(
                    "SELECT code, paired_code FROM txn_type_attributes"
                    " WHERE paired_code IS NOT NULL"
                )
            ).all()
        )

    assert pairs, "짝이 적힌 줄이 하나도 없다 — 시드가 비었거나 짝이 사라졌다"

    one_way = [
        f"{code} → {partner}({pairs.get(partner, '없음')})"
        for code, partner in pairs.items()
        if pairs.get(partner) != code
    ]

    assert not one_way, "짝이 서로를 가리키지 않는다: " + ", ".join(sorted(one_way))


# ── 기준과 코드가 맞물리는가 ────────────────────────────────────────────────
#
# 검사원이 코드를 고르면 그 항목의 기준(규격 · 중심선 · 경고선)이 딸려 와야
# 한다. 코드는 있는데 기준이 없으면 무엇을 보고 판정하는지 표가 말하지 못하고,
# 기준은 있는데 코드가 없으면 불합격을 적을 수 없는 항목이 남는다.
#
# **두 방향 다 본다.** 한쪽만 보면 반대쪽으로 샌다.


def _stage_rules(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        return [
            (str(row[0]), str(row[1]))
            for row in conn.execute(
                text("SELECT reason_code, stage_code FROM nonconformity_stage_rules")
            )
        ]


def _reason_items(engine: Engine) -> dict[str, tuple[str, str | None]]:
    with engine.connect() as conn:
        return {
            str(row[0]): (str(row[1]), row[2])
            for row in conn.execute(
                text(
                    "SELECT code, measure_kind, inspection_item_code"
                    "  FROM nonconformity_attributes"
                )
            )
        }


def _standards(engine: Engine) -> set[tuple[str, str]]:
    with engine.connect() as conn:
        return {
            (str(row[0]), str(row[1]))
            for row in conn.execute(
                text("SELECT process_code, item_code FROM process_inspection_standards")
            )
        }


def test_every_usable_reason_has_a_standard_to_read(blank: Engine) -> None:
    """**코드를 고르면 기준이 딸려 와야 한다.**

    어느 단계에서 쓸 수 있는 계량 코드가 가리키는 항목은, 그 단계가 쓰는 공정의
    기준 표에 있어야 한다. 없으면 검사원이 고를 수는 있는데 규격도 중심선도
    나오지 않는다.
    """
    seed_module.seed(blank)
    reasons = _reason_items(blank)
    standards = _standards(blank)

    missing = []
    for reason_code, stage_code in _stage_rules(blank):
        if stage_code == codes.RETEST_STAGE:
            continue
        kind, item = reasons[reason_code]
        if kind != codes.MEASURED_KIND or item is None:
            continue
        for process in codes.STAGE_PROCESSES[stage_code]:
            if (process, item) in standards:
                break
        else:
            missing.append(f"{reason_code}({item}) × {stage_code}")

    assert not missing, "기준 없이 쓸 수 있는 코드: " + ", ".join(sorted(missing))


def test_every_standard_has_a_reason_that_can_use_it(blank: Engine) -> None:
    """반대 방향 — **잴 수는 있는데 불합격을 적을 수 없는 항목**이 없어야 한다.

    「폭」과 「치수」를 항목에서 뺀 잣대가 이것이다. 기준만 있고 그것을 가리키는
    코드가 없으면 그 줄은 아무도 읽지 않는다.
    """
    seed_module.seed(blank)
    reasons = _reason_items(blank)
    rules = _stage_rules(blank)

    usable: set[tuple[str, str]] = set()
    for reason_code, stage_code in rules:
        if stage_code == codes.RETEST_STAGE:
            continue
        _, item = reasons[reason_code]
        if item is None:
            continue
        for process in codes.STAGE_PROCESSES[stage_code]:
            usable.add((process, item))

    unreachable = sorted(f"{process} × {item}" for process, item in _standards(blank) - usable)
    assert not unreachable, "가리키는 코드가 없는 기준: " + ", ".join(unreachable)


def test_a_retest_only_looks_at_what_time_can_change(blank: Engine) -> None:
    """**재검사는 시간이 바꾸는 것만 본다.**

    만료 로트가 돌아와 다시 보는 항목은 경시 변화가 켜진 것뿐이다. 켜지지 않은
    항목까지 보면 22판이 좁혀 둔 범위가 되돌아간다 — 그리고 그것은 규칙이
    아니라 데이터로 지켜져야 한다.
    """
    seed_module.seed(blank)
    reasons = _reason_items(blank)

    with blank.connect() as conn:
        time_variant = {
            str(row[0])
            for row in conn.execute(
                text(
                    "SELECT DISTINCT item_code FROM process_inspection_standards"
                    " WHERE time_variant"
                )
            )
        }

    offenders = [
        reason_code
        for reason_code, stage_code in _stage_rules(blank)
        if stage_code == codes.RETEST_STAGE
        and (item := reasons[reason_code][1]) is not None
        and item not in time_variant
    ]

    assert not offenders, "재검사에 걸린 비경시 항목: " + ", ".join(sorted(offenders))


def test_there_are_sixteen_inspection_items(blank: Engine) -> None:
    """설계도는 18, 공정별 표는 17, **불합격을 적을 수 있는 것만 세면 16**이다."""
    seed_module.seed(blank)

    assert _count(blank, "common_codes", "group_code = 'INSP_ITEM'") == 16


# ── 자재군 ──────────────────────────────────────────────────────────────────


def test_every_raw_material_belongs_to_a_group(blank: Engine) -> None:
    """원자재 열다섯이 전부 무리를 갖는다 — 분체 다섯 · 액상수지 여섯 · 시트필름 넷."""
    seed_module.seed(blank)

    assert _count(blank, "items", "item_type = '원자재' AND material_group IS NULL") == 0
    assert _count(blank, "items", "material_group = '분체'") == 5
    assert _count(blank, "items", "material_group = '액상수지'") == 6
    assert _count(blank, "items", "material_group = '시트필름'") == 4


def test_nothing_but_raw_materials_belongs_to_a_group(blank: Engine) -> None:
    """반제품과 완제품에는 자재군이 없다."""
    seed_module.seed(blank)

    assert _count(blank, "items", "item_type <> '원자재' AND material_group IS NOT NULL") == 0


def test_a_powder_is_not_asked_for_viscosity(blank: Engine) -> None:
    """**이 조각이 있는 이유다.**

    자재군이 서기 전에는 「수입」 기준 여덟이 원자재 열다섯 전부에 똑같이 걸렸다 —
    분말에 점도를, 라이너에 입도를 재라고 내미는 셈이었다. 이제 무리마다 볼 것만
    선다.
    """
    seed_module.seed(blank)

    powder = "process_code = '수입' AND material_group = '분체'"
    liquid = "process_code = '수입' AND material_group = '액상수지'"
    sheet = "process_code = '수입' AND material_group = '시트필름'"

    # 분말에 점도를 재라고 하지 않는다. 라이너에 입도를 재라고 하지 않는다.
    assert (
        _count(blank, "process_inspection_standards", f"{powder} AND item_code = '점도'") == 0
    )
    assert _count(blank, "process_inspection_standards", f"{sheet} AND item_code = '입도'") == 0
    # 대신 무리가 실제로 갖는 것은 선다.
    assert (
        _count(blank, "process_inspection_standards", f"{powder} AND item_code = '입도'") == 1
    )
    assert (
        _count(blank, "process_inspection_standards", f"{liquid} AND item_code = '점도'") == 1
    )
    assert _count(blank, "process_inspection_standards", f"{sheet} AND item_code = '두께'") == 1


def test_every_group_is_checked_for_the_three_counted_items(blank: Engine) -> None:
    """이물 · 포장 · 성적서는 세는 것이라 무리를 가리지 않는다 — 셋 모두 본다."""
    seed_module.seed(blank)

    for counted in ("이물", "포장", "성적서"):
        assert (
            _count(
                blank,
                "process_inspection_standards",
                f"process_code = '수입' AND item_code = '{counted}'",
            )
            == 3
        ), f"{counted} 가 세 무리 전부에 서지 않았다"


def test_no_process_standard_carries_a_material_group(blank: Engine) -> None:
    """공정검사 기준은 자재군을 갖지 않는다 — 반제품과 완제품을 보기 때문이다."""
    seed_module.seed(blank)

    assert (
        _count(
            blank,
            "process_inspection_standards",
            "process_code <> '수입' AND material_group IS NOT NULL",
        )
        == 0
    )


def test_every_measured_standard_says_in_what_unit(blank: Engine) -> None:
    """**재는 값에는 단위가 있다** (CodeRabbit 리뷰 NC-123).

    시드는 이미 그렇게 서 있었다 — 규격 있는 기준은 전부 단위를 갖고, 규격 없는
    것(세는 항목)만 비어 있다. **그것이 우연이 아니라 규칙임을** CHECK 가 걸고
    이 검사가 시드 쪽에서 잰다.

    이것이 새면 판정 시점의 단위를 잠그는 외래키가 **그 줄에서 통째로
    건너뛰어진다** — 복합 외래키는 한 칸이라도 `NULL` 이면 검사하지 않는다.
    """
    seed_module.seed(blank)

    assert (
        _count(
            blank,
            "process_inspection_standards",
            "(upper_spec_limit IS NOT NULL OR lower_spec_limit IS NOT NULL)"
            " AND unit IS NULL",
        )
        == 0
    )


def test_no_counted_reason_points_at_a_measured_standard(blank: Engine) -> None:
    """**사유가 계수라고 말하는 항목은 기준도 계수여야 한다** (Codex 리뷰 NC-125).

    갈리면 그 사유로 **규격 안인데 불합격**을 만들 수 있다 — 사람이 계산을
    덮는 자리이고 원칙 ③ 이 없애려는 것이다. 쓰기 경로가 요청을 거절하지만
    **거절이 나는 것 자체가 기준정보가 어긋났다는 뜻**이라, 시드 쪽에서도
    잰다.
    """
    seed_module.seed(blank)

    assert (
        _count(
            blank,
            "nonconformity_attributes AS a"
            " JOIN process_inspection_standards AS s"
            " ON s.item_code = a.inspection_item_code AND s.process_code = '수입'",
            "a.measure_kind = '계수' AND a.inspection_item_code IS NOT NULL"
            " AND (s.upper_spec_limit IS NOT NULL OR s.lower_spec_limit IS NOT NULL)",
        )
        == 0
    )
