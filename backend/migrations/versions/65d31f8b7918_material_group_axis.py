"""자재군 축 — 수입 기준이 품목을 가리게 한다

「수입」 기준 여덟이 원자재 열다섯 전부에 똑같이 걸리던 자리를 닫는다. 분말에
점도를, 라이너에 입도를 재라고 내밀지 않게 된다.

**자동 생성을 그대로 쓰지 않았다.** Alembic 이 내놓은 것에는 CHECK 넷이 전부
없었고(CHECK 는 비교 대상이 아니다), 기준 표의 **기본키 교체**도 없었다 —
`id` 를 더하기만 하고 옛 기본키를 그대로 두었다. 손으로 다시 적었고
`tests/test_migrations.py` 가 두 스키마를 견준다.

**데이터 단계가 있다.** 스키마만 바꾸면 이미 심긴 데이터베이스는 자재군이
`NULL` 인 「수입」 줄을 들고 있어 새 CHECK 에 걸린다. 그래서 기준정보를 여기서
옮긴다 — `CLAUDE.md` 가 「기준정보 값을 고쳐야 하면 시드가 아니라
마이그레이션으로 낸다」고 적은 그 자리다.

**지우지 않고 옮긴다.** 이 마이그레이션이 존재하는 근거가 「사람이 고친 값을
재시드가 덮어쓰는 쪽이 더 큰 사고다」인데, 지우고 다시 심으면 그 재시드와 같은
일을 하게 된다. 그래서 옛 여덟 줄을 `UPDATE` 로 첫 무리에 옮기고, 두 무리
이상에 걸치는 항목만 **그 줄을 베껴** 나머지 무리에 세운다. 실측 σ 나 고객이
준 규격이 들어 있었다면 그대로 따라간다. 되돌릴 때도 같다 — 베낀 줄만 지우고
남은 줄의 값은 건드리지 않는다.

**데이터 단계는 이미 심긴 데이터베이스에서만 돈다.** 조건은 시드의 조건 ③ 을
뒤집은 것이다 — 시드는 품목 표가 **비어 있을 때** 돌고 이것은 **비어 있지 않을
때** 돈다. 둘은 같은 데이터베이스에서 함께 돌 수 없으므로 값이 두 번 들어가지
않는다.

Revision ID: 65d31f8b7918
Revises: 3c602ffaebc3
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "65d31f8b7918"
down_revision: str | None = "3c602ffaebc3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 이미 심긴 데이터베이스에서만 도는 데이터 단계의 조건. 시드의 조건 ③ 을 뒤집은 것.
_ALREADY_SEEDED = "WHERE EXISTS (SELECT 1 FROM items)"

# 원자재 열다섯이 어느 무리인가. 재고단위가 경계를 말한다 — KG 아홉 · L 둘 · M2 넷.
# **시드 SQL 과 같은 것을 말한다.** 둘이 갈리지 않는지는
# `test_both_roads_reach_the_same_material_groups` 가 두 길을 실제로 돌려 견준다.
_ITEM_GROUPS = """('RM-01','액상수지'),('RM-02','분체'),('RM-03','분체'),('RM-04','시트필름'),
       ('RM-05','액상수지'),('RM-06','분체'),('RM-07','시트필름'),('RM-08','액상수지'),
       ('RM-09','분체'),('RM-10','액상수지'),('RM-11','시트필름'),('RM-12','분체'),
       ('RM-13','액상수지'),('RM-14','액상수지'),('RM-15','시트필름')"""

# 검사항목이 **처음** 서는 무리. 옛 줄을 이 무리로 옮기므로 그 줄의 값이 따라간다.
_FIRST_GROUP = """('입도','분체'),('수분','분체'),('점도','액상수지'),('색차','액상수지'),
       ('두께','시트필름'),('이물','분체'),('포장','분체'),('성적서','분체')"""

# 두 무리 이상에 걸치는 항목의 **나머지** 무리. 첫 무리의 줄을 베껴 세운다.
# 계수 셋(이물 · 포장 · 성적서)은 재는 것이 아니라 세는 것이라 무리를 가리지 않는다.
_EXTRA_GROUPS = """('수분','액상수지'),('색차','시트필름'),
       ('이물','액상수지'),('이물','시트필름'),
       ('포장','액상수지'),('포장','시트필름'),
       ('성적서','액상수지'),('성적서','시트필름')"""

# 옮기지 못한 줄이 있으면 **무엇이 남았는지 말하고 멈춘다.** 그냥 두면 바로 뒤의
# 양방향 CHECK 가 대신 터지는데, 그 오류는 「제약 위반」일 뿐이라 원인이 위의 두
# 목록에 있다는 것을 말해 주지 않는다. 트랜잭션 하나이므로 멈추면 아무것도 남지 않는다.
_STOP_IF_ANYTHING_WAS_LEFT_BEHIND = """
DO $$
DECLARE leftover text;
BEGIN
  SELECT string_agg(DISTINCT code, ', ') INTO leftover
    FROM items WHERE item_type = '원자재' AND material_group IS NULL;
  IF leftover IS NOT NULL THEN
    RAISE EXCEPTION '자재군을 정하지 못한 원자재가 있다: % — 이 리비전의 _ITEM_GROUPS 에 더해야 한다', leftover;
  END IF;

  SELECT string_agg(DISTINCT item_code, ', ') INTO leftover
    FROM process_inspection_standards WHERE process_code = '수입' AND material_group IS NULL;
  IF leftover IS NOT NULL THEN
    RAISE EXCEPTION '자재군을 정하지 못한 수입 검사항목이 있다: % — 이 리비전의 _FIRST_GROUP 에 더해야 한다', leftover;
  END IF;
END $$;
"""

# **되돌리기가 조용히 지우지 못하게 막는다.**
#
# 옛 기본키 `(공정, 검사항목)` 이 돌아오므로 항목마다 한 줄로 줄이는 것 **자체는
# 피할 수 없다.** 피할 수 있는 것은 **조용한 것**이다 — upgrade 가 멈출 때 이유를
# 말하는데 downgrade 는 아무 말도 하지 않았다.
#
# 둘을 본다: 이 리비전이 세우지 않은 줄(남이 더한 것)과, 남길 한 줄이 아닌 자리에
# 들어 있는 실측 σ(잰 사실). 둘 다 「일어난 일은 지우지 않는다」에 걸린다.
_STOP_IF_DOWNGRADE_WOULD_LOSE_SOMETHING = f"""
DO $$
DECLARE doomed text;
BEGIN
  SELECT string_agg(DISTINCT item_code || '/' || material_group, ', ') INTO doomed
    FROM process_inspection_standards
   WHERE process_code = '수입'
     AND (item_code, material_group) NOT IN (
           SELECT f.item, f.grp FROM (VALUES {_FIRST_GROUP}) AS f(item, grp)
           UNION ALL
           SELECT e.item, e.grp FROM (VALUES {_EXTRA_GROUPS}) AS e(item, grp)
         );
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 이 리비전이 세우지 않은 수입 기준이 사라진다: % — 남이 더한 줄이다. 지울지 옮길지는 사람이 정한다', doomed;
  END IF;

  SELECT string_agg(DISTINCT item_code || '/' || material_group, ', ') INTO doomed
    FROM process_inspection_standards s
   WHERE s.process_code = '수입' AND s.sigma IS NOT NULL
     AND s.id <> (SELECT min(t.id) FROM process_inspection_standards t
                   WHERE t.process_code = '수입' AND t.item_code = s.item_code);
  IF doomed IS NOT NULL THEN
    RAISE EXCEPTION '되돌리면 실측 σ 가 사라진다: % — 옛 기본키가 항목마다 한 줄만 받으므로 줄이는 것은 피할 수 없다. 남길 줄로 옮긴 뒤 다시 되돌린다', doomed;
  END IF;
END $$;
"""


# 그룹이 이미 있어도 **뜻이 같으면** 넘어간다. 다른 것은 `value_fixed` 하나뿐인데,
# 그것이 참이면 「프로그램이 값을 보고 분기한다」는 뜻이라 자재군과 정반대다 —
# 넘어가면 화면에서 무리를 못 늘리게 된다. 그때는 이름을 말하고 멈춘다.
_STOP_IF_THE_GROUP_MEANS_SOMETHING_ELSE = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM code_groups WHERE group_code = 'MATERIAL_GROUP' AND value_fixed) THEN
    RAISE EXCEPTION 'MATERIAL_GROUP 그룹이 이미 있는데 value_fixed 가 참이다 — 자재군은 값이 늘 수 있는 그룹이어야 한다. 먼저 사람이 정한다';
  END IF;
END $$;
"""


_STANDARD_VALUE_COLUMNS = (
    "upper_spec_limit, lower_spec_limit, center_line, warning_ratio,"
    " sigma, sigma_source, time_variant, unit"
)


def upgrade() -> None:
    # ── 품목이 자기 무리를 안다 ─────────────────────────────────────────────
    op.add_column("items", sa.Column("material_group", sa.String(length=30), nullable=True))
    op.add_column(
        "items",
        sa.Column(
            "material_group_group",
            sa.String(length=20),
            server_default="MATERIAL_GROUP",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_item_material_group",
        "items",
        "common_codes",
        ["material_group_group", "material_group"],
        ["group_code", "code"],
    )
    op.create_check_constraint(
        "ck_item_material_group_group", "items", "material_group_group = 'MATERIAL_GROUP'"
    )

    # ── 기준 표가 자재군을 받는다 ───────────────────────────────────────────
    op.add_column(
        "process_inspection_standards",
        sa.Column("material_group", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "process_inspection_standards",
        sa.Column(
            "material_group_group",
            sa.String(length=20),
            server_default="MATERIAL_GROUP",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_inspection_standard_material_group",
        "process_inspection_standards",
        "common_codes",
        ["material_group_group", "material_group"],
        ["group_code", "code"],
    )
    op.create_check_constraint(
        "ck_inspection_standard_material_group_group",
        "process_inspection_standards",
        "material_group_group = 'MATERIAL_GROUP'",
    )

    # ── 기본키를 대리키로 바꾼다 ────────────────────────────────────────────
    # 정체성은 (공정 × 검사항목 × 자재군)이지만 기본키는 `NULL` 을 받지 않고,
    # 공정검사 줄의 자재군은 비어 있다. 자리만 맡는 `id` 를 두고 정체성은 아래의
    # 유일키가 말한다. `SERIAL` 이라 이미 있는 줄에도 번호가 채워진다.
    op.execute(
        "ALTER TABLE process_inspection_standards DROP CONSTRAINT process_inspection_standards_pkey"
    )
    op.execute("ALTER TABLE process_inspection_standards ADD COLUMN id SERIAL PRIMARY KEY")

    # ── 데이터 — 이미 심긴 데이터베이스에서만 돈다 ─────────────────────────
    # **이미 있으면 넘어간다.** 자재군은 「값이 늘 수 있는 그룹」이라 운영자가 먼저
    # 만들어 두었을 수 있다. 그대로 `INSERT` 하면 「제약 위반」만 보이고 원인이
    # 이 리비전에 있다는 것을 말해 주지 않는다 — upgrade 가 멈출 때 이유를 말하기로
    # 한 것과 같은 자리다.
    op.execute(_STOP_IF_THE_GROUP_MEANS_SOMETHING_ELSE)
    op.execute(
        "INSERT INTO code_groups (group_code, name, value_fixed, description)"
        " SELECT 'MATERIAL_GROUP', '자재군', FALSE, '수입 검사 기준이 걸리는 축이다.'"
        f" {_ALREADY_SEEDED}"
        "   AND NOT EXISTS (SELECT 1 FROM code_groups WHERE group_code = 'MATERIAL_GROUP')"
    )
    op.execute(
        "INSERT INTO common_codes (group_code, code, name, sort_order, description)"
        " SELECT v.group_code, v.code, v.name, v.sort_order, v.description FROM (VALUES"
        " ('MATERIAL_GROUP','분체','분체',1,'입도와 수분을 본다'),"
        " ('MATERIAL_GROUP','액상수지','액상 · 수지',2,'점도와 색차를 본다'),"
        " ('MATERIAL_GROUP','시트필름','시트 · 필름',3,'두께와 색차를 본다')"
        " ) AS v(group_code, code, name, sort_order, description)"
        f" {_ALREADY_SEEDED}"
        "   AND NOT EXISTS (SELECT 1 FROM common_codes c"
        "                    WHERE c.group_code = v.group_code AND c.code = v.code)"
    )
    op.execute(
        "UPDATE items SET material_group = m.grp"
        f" FROM (VALUES {_ITEM_GROUPS}) AS m(code, grp)"
        " WHERE items.code = m.code"
    )
    # 옛 줄을 **옮긴다.** 지우지 않으므로 그 줄에 들어 있던 값이 따라간다.
    op.execute(
        "UPDATE process_inspection_standards s SET material_group = m.grp"
        f" FROM (VALUES {_FIRST_GROUP}) AS m(item, grp)"
        " WHERE s.process_code = '수입' AND s.item_code = m.item"
    )
    # 두 무리 이상에 걸치는 항목만 **그 줄을 베껴** 나머지 무리에 세운다.
    #
    # **규격은 따라가고 σ 는 따라가지 않는다.** 규격 상·하한과 중심선은 고객이
    # 정하는 것이라 같은 항목이면 무리가 달라도 그대로 쓸 수 있다. σ 는 **잰
    # 값**이고 새 무리에서는 잰 적이 없다 — 베껴 오면 재지 않은 것을 쟀다고
    # 적는 것이 된다. 그래서 「미정」으로 세운다(σ 와 출처를 묶는 양방향 CHECK
    # 가 그 짝을 지킨다).
    op.execute(
        "INSERT INTO process_inspection_standards"
        " (process_group, process_code, item_group, item_code, material_group,"
        f"  material_group_group, {_STANDARD_VALUE_COLUMNS})"
        " SELECT s.process_group, s.process_code, s.item_group, s.item_code, m.grp,"
        "        s.material_group_group, s.upper_spec_limit, s.lower_spec_limit, s.center_line,"
        "        s.warning_ratio, NULL, '미정', s.time_variant, s.unit"
        "   FROM process_inspection_standards s"
        f"   JOIN (VALUES {_EXTRA_GROUPS}) AS m(item, grp) ON s.item_code = m.item"
        "  WHERE s.process_code = '수입' AND s.material_group IS NOT NULL"
    )
    op.execute(_STOP_IF_ANYTHING_WAS_LEFT_BEHIND)

    # ── 데이터가 자리를 잡은 뒤에 규칙을 건다 ───────────────────────────────
    # 순서가 뒤집히면 옛 줄이 새 CHECK 에 걸려 마이그레이션이 멈춘다.
    op.create_check_constraint(
        "ck_item_material_group_matches_type",
        "items",
        "(item_type = '원자재') = (material_group IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_inspection_standard",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group"],
        postgresql_nulls_not_distinct=True,
    )
    op.create_check_constraint(
        "ck_inspection_standard_material_group_matches_process",
        "process_inspection_standards",
        "(process_code IN ('수입')) = (material_group IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_inspection_standard_material_group_matches_process",
        "process_inspection_standards",
        type_="check",
    )
    op.drop_constraint("uq_inspection_standard", "process_inspection_standards", type_="unique")
    op.drop_constraint("ck_item_material_group_matches_type", "items", type_="check")

    op.execute(_STOP_IF_DOWNGRADE_WOULD_LOSE_SOMETHING)

    # **항목마다 가장 먼저 선 줄 하나만 남기고 나머지를 지운다.**
    #
    # 앞의 주석은 「베낀 줄만 지운다」고 말했는데 그것은 사실이 아니었다 — 조건은
    # `id` 가 최솟값이 아닌 **전부**라서, 이 리비전이 베끼지 않은 줄도 함께
    # 지웠다. 남는 한 줄이 옮겨 쓴 옛 줄이라 사람이 고친 값이 거기 있다는 것은
    # 맞지만, 그 밖의 줄에 있던 값은 사라진다.
    #
    # 줄이는 것 자체는 피할 수 없다(옛 기본키가 항목마다 한 줄만 받는다). 그래서
    # 위에서 **무엇이 사라지는지 먼저 말하고 멈춘다.**
    op.execute(
        "DELETE FROM process_inspection_standards s"
        " WHERE s.process_code = '수입'"
        "   AND s.id <> (SELECT min(t.id) FROM process_inspection_standards t"
        "                 WHERE t.process_code = '수입' AND t.item_code = s.item_code)"
    )
    op.execute(
        "UPDATE process_inspection_standards SET material_group = NULL WHERE process_code = '수입'"
    )

    op.execute(
        "ALTER TABLE process_inspection_standards DROP CONSTRAINT process_inspection_standards_pkey"
    )
    op.drop_column("process_inspection_standards", "id")
    op.execute(
        "ALTER TABLE process_inspection_standards ADD PRIMARY KEY (process_code, item_code)"
    )

    op.drop_constraint(
        "ck_inspection_standard_material_group_group",
        "process_inspection_standards",
        type_="check",
    )
    op.drop_constraint(
        "fk_inspection_standard_material_group",
        "process_inspection_standards",
        type_="foreignkey",
    )
    op.drop_column("process_inspection_standards", "material_group_group")
    op.drop_column("process_inspection_standards", "material_group")

    op.drop_constraint("ck_item_material_group_group", "items", type_="check")
    op.drop_constraint("fk_item_material_group", "items", type_="foreignkey")
    op.drop_column("items", "material_group_group")
    op.drop_column("items", "material_group")

    # **코드는 맨 마지막에, 심은 셋만 지운다.**
    #
    # 가리키는 칸을 먼저 걷어내야 지울 수 있다 — 순서를 바꾸면 외래키가 막는다.
    # 그리고 자재군은 「값이 늘 수 있는 그룹」이므로 올린 뒤에 넷째 무리가 늘었을
    # 수 있다. 그룹째 지우면 사람이 넣은 사실이 함께 사라지므로, 이 리비전이 심은
    # 셋만 지우고 그룹은 **남은 값이 없을 때만** 지운다.
    op.execute(
        "DELETE FROM common_codes WHERE group_code = 'MATERIAL_GROUP'"
        " AND code IN ('분체', '액상수지', '시트필름')"
    )
    op.execute(
        "DELETE FROM code_groups WHERE group_code = 'MATERIAL_GROUP'"
        " AND NOT EXISTS (SELECT 1 FROM common_codes WHERE group_code = 'MATERIAL_GROUP')"
    )
