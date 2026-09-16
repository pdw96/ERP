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
_ITEM_GROUPS = """('RM-01','액상수지'),('RM-02','분체'),('RM-03','분체'),('RM-04','시트필름'),
       ('RM-05','액상수지'),('RM-06','분체'),('RM-07','시트필름'),('RM-08','액상수지'),
       ('RM-09','분체'),('RM-10','액상수지'),('RM-11','시트필름'),('RM-12','분체'),
       ('RM-13','액상수지'),('RM-14','액상수지'),('RM-15','시트필름')"""

# **첫 줄에 형을 박는 이유.** `VALUES` 목록에서 PostgreSQL 은 전부 `NULL` 인 열을
# `text` 로 추론하고, `sigma` 가 그것이다 — 박지 않으면 「double precision 인데
# text 가 왔다」로 마이그레이션이 멈춘다. 첫 줄만 박으면 나머지가 따라온다.
# 자재군이 선 뒤의 수입 기준 열여섯. 규격 숫자는 옛 여덟 줄에서 그대로 옮겼다 —
# 상·하한은 항목이 갖는 것이지 무리가 갖는 것이 아니다.
_INCOMING_STANDARDS = """
  ('PROCESS','수입','INSP_ITEM','입도',  '분체',    'MATERIAL_GROUP',   50.0::double precision,   10.0::double precision,   30.0::double precision, 0.70::double precision, NULL::double precision, '미정', FALSE, 'µm'),
  ('PROCESS','수입','INSP_ITEM','수분',  '분체',    'MATERIAL_GROUP',    0.50,  NULL,    0.20, 0.70, NULL, '미정', TRUE,  '%'),
  ('PROCESS','수입','INSP_ITEM','이물',  '분체',    'MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','포장',  '분체',    'MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', TRUE,  NULL),
  ('PROCESS','수입','INSP_ITEM','성적서','분체',    'MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','점도',  '액상수지','MATERIAL_GROUP', 4000.0, 2000.0, 3000.0, 0.70, NULL, '미정', TRUE,  'cP'),
  ('PROCESS','수입','INSP_ITEM','수분',  '액상수지','MATERIAL_GROUP',    0.50,  NULL,    0.20, 0.70, NULL, '미정', TRUE,  '%'),
  ('PROCESS','수입','INSP_ITEM','색차',  '액상수지','MATERIAL_GROUP',    1.00,  NULL,    0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  ('PROCESS','수입','INSP_ITEM','이물',  '액상수지','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','포장',  '액상수지','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', TRUE,  NULL),
  ('PROCESS','수입','INSP_ITEM','성적서','액상수지','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','두께',  '시트필름','MATERIAL_GROUP',  105.0,   95.0,  100.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS','수입','INSP_ITEM','색차',  '시트필름','MATERIAL_GROUP',    1.00,  NULL,    0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  ('PROCESS','수입','INSP_ITEM','이물',  '시트필름','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','포장',  '시트필름','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', TRUE,  NULL),
  ('PROCESS','수입','INSP_ITEM','성적서','시트필름','MATERIAL_GROUP',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL)
"""

# 자재군이 서기 전의 수입 기준 여덟. 되돌릴 때 쓴다.
_INCOMING_STANDARDS_BEFORE = """
  ('PROCESS','수입','INSP_ITEM','입도',   50.0::double precision,   10.0::double precision,   30.0::double precision, 0.70::double precision, NULL::double precision, '미정', FALSE, 'µm'),
  ('PROCESS','수입','INSP_ITEM','수분',    0.50,  NULL,    0.20, 0.70, NULL, '미정', TRUE,  '%'),
  ('PROCESS','수입','INSP_ITEM','점도', 4000.0, 2000.0, 3000.0, 0.70, NULL, '미정', TRUE,  'cP'),
  ('PROCESS','수입','INSP_ITEM','두께',  105.0,   95.0,  100.0, 0.70, NULL, '미정', FALSE, 'µm'),
  ('PROCESS','수입','INSP_ITEM','색차',    1.00,  NULL,    0.30, 0.70, NULL, '미정', TRUE,  'ΔE'),
  ('PROCESS','수입','INSP_ITEM','이물',   NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL),
  ('PROCESS','수입','INSP_ITEM','포장',   NULL,   NULL,   NULL, 0.70, NULL, '미정', TRUE,  NULL),
  ('PROCESS','수입','INSP_ITEM','성적서', NULL,   NULL,   NULL, 0.70, NULL, '미정', FALSE, NULL)
"""


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
    op.execute(
        "INSERT INTO code_groups (group_code, name, value_fixed, description)"
        " SELECT 'MATERIAL_GROUP', '자재군', FALSE, '수입 검사 기준이 걸리는 축이다.'"
        f" {_ALREADY_SEEDED}"
    )
    op.execute(
        "INSERT INTO common_codes (group_code, code, name, sort_order, description)"
        " SELECT v.group_code, v.code, v.name, v.sort_order, v.description FROM (VALUES"
        " ('MATERIAL_GROUP','분체','분체',1,'입도와 수분을 본다'),"
        " ('MATERIAL_GROUP','액상수지','액상 · 수지',2,'점도와 색차를 본다'),"
        " ('MATERIAL_GROUP','시트필름','시트 · 필름',3,'두께와 색차를 본다')"
        " ) AS v(group_code, code, name, sort_order, description)"
        f" {_ALREADY_SEEDED}"
    )
    op.execute(
        "UPDATE items SET material_group = m.grp"
        f" FROM (VALUES {_ITEM_GROUPS}) AS m(code, grp)"
        " WHERE items.code = m.code"
    )
    # 옛 여덟 줄은 자재군을 가질 수 없다 — 셋으로 갈려야 뜻이 생긴다. 지우고 다시 심는다.
    op.execute("DELETE FROM process_inspection_standards WHERE process_code = '수입'")
    op.execute(
        "INSERT INTO process_inspection_standards"
        " (process_group, process_code, item_group, item_code, material_group, material_group_group,"
        "  upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit)"
        f" SELECT v.* FROM (VALUES {_INCOMING_STANDARDS}) AS v"
        " (process_group, process_code, item_group, item_code, material_group, material_group_group,"
        "  upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit)"
        f" {_ALREADY_SEEDED}"
    )

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

    # 열여섯 줄을 그냥 두면 자재군을 뺀 순간 (공정 × 검사항목)이 겹쳐 옛 기본키가
    # 서지 못한다 — 수분과 색차가 두 무리에 걸쳐 있기 때문이다. 지우고 옛 여덟을 심는다.
    op.execute("DELETE FROM process_inspection_standards WHERE process_code = '수입'")
    op.execute(
        "INSERT INTO process_inspection_standards"
        " (process_group, process_code, item_group, item_code,"
        "  upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit)"
        f" SELECT v.* FROM (VALUES {_INCOMING_STANDARDS_BEFORE}) AS v"
        " (process_group, process_code, item_group, item_code,"
        "  upper_spec_limit, lower_spec_limit, center_line, warning_ratio, sigma, sigma_source, time_variant, unit)"
        f" {_ALREADY_SEEDED}"
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

    # **코드는 맨 마지막에 지운다.** 품목과 기준이 아직 가리키고 있을 때 지우면
    # 외래키가 막는다 — 실제로 여기서 한 번 막혔다. 가리키는 칸을 먼저 걷어낸
    # 뒤라야 가리켜지던 줄을 지울 수 있다.
    op.execute("DELETE FROM common_codes WHERE group_code = 'MATERIAL_GROUP'")
    op.execute("DELETE FROM code_groups WHERE group_code = 'MATERIAL_GROUP'")
