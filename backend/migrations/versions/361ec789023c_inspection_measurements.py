"""측정값 줄 — 판정 시점의 규격을 박아 둔다

표 하나(`inspection_measurements`)를 세우고, 그 표가 기댈 **결속 셋**을 앞의 두
표에 붙인다 — `items` 에 유일키 하나, `inspections` 에 칸 하나와 유일키 하나와
외래키 하나.

**그 결속이 이 리비전의 절반이다.** 측정 줄이 「그 무리의 기준」만 가리키게
하려면 품목 → 검사 → 기준이 **같은 자재군**을 말해야 하고, 그 사슬의 가운데가
`inspections.material_group` 이다. 검사 기록을 세울 때 이 칸이 없었던 것은 그때
가리키는 쪽이 없었기 때문이다 — 부르는 쪽이 없는 칸을 미리 두지 않는다.

**자동 생성을 그대로 쓰지 않았다. 두 자리가 틀렸다.**

- **순서가 거꾸로였다.** 측정 표를 먼저 만들고 `inspections.material_group` 을
  뒤에 붙였는데, 그 표의 외래키가 바로 그 칸을 가리킨다. 그대로 돌리면 없는
  칸을 가리키다 멈춘다
- **`NOT NULL` 칸을 한 번에 붙였다.** 줄이 하나라도 있으면 그 자리에서 터진다.
  비었다고 **가정하지 않고** 비울 수 없게 적는다 — 널 허용으로 붙이고, 품목에서
  값을 끌어와 채우고, 그 다음에 `NOT NULL` 로 조인다

`downgrade()` 의 순서도 손으로 되돌렸다. 자동 생성은 `items` 의 유일키를 먼저
떼려 했는데, 그것을 가리키는 외래키가 아직 `inspections` 에 붙어 있다.

**데이터 단계가 있다 — 채우는 `UPDATE` 하나.** 값을 **지어내지 않는다**:
품목이 이미 아는 자재군을 그대로 끌어온다. 끌어올 수 없는 줄이 있으면 그 줄은
원자재가 아니라는 뜻이고, 검사 기록의 CHECK 가 그런 줄을 애초에 막는다.

**`downgrade()` 가 측정값을 통째로 지운다. 그래서 멈추고 이름을 말한다.** 되돌릴
수 없다 — 실측값과 **그때 쓴 규격**이 함께 사라지고 복구할 방법은 백업뿐이다.
처음에는 「이 리비전이 세운 표라 사람이 먼저 넣어 둔 값이 있을 수 없다」고 적고
멈추지 않았는데, **표가 내 것인 것과 줄이 내 것인 것은 다르다** — `create_table`
은 줄을 하나도 만들지 않는다.

**`inspections.material_group` 은 다르다 — 조용히 내려간다.** 그 칸의 값은 사람의
것이 아니라 품목에서 끌어온 파생이고, **다시 만들 수 있다는 주장의 근거를 이름으로
적는다**: `fk_inspection_item`(품목이 실재한다) · `ck_inspection_item_is_raw_material`
(원자재다) · `ck_item_material_group_matches_type`(원자재면 자재군이 있다). 셋 중
하나가 느슨해지는 날 이 주장은 **조용히 거짓이 된다** — 그래서 근거를 적는다.

**올릴 때 잠근다.**

- `items` · `inspections` 의 유일키 — 잠금을 잡고 인덱스를 만든다.
  `CONCURRENTLY` 를 쓸 수 없는 형태다
- `inspections` 의 `SET NOT NULL` — **기존 행 전체를 검사한다**
- 외래키는 **가리키는 표와 가리켜지는 표 양쪽을 잡는다.** 이 리비전의 외래키가
  가리키는 표는 전부 함께 잠겨 그동안 쓰기가 멈춘다 — 목록을 세지 않는다. 세면
  갈리고, 실제로 갈려서 `process_inspection_standards` 가 빠져 있었다
- `ADD COLUMN` 은 기본값이 없어 표를 다시 쓰지 않는다(PostgreSQL 11 이후)

`migrations/env.py` 가 전체를 트랜잭션 하나로 감싸므로 첫 `ALTER` 가 잡은 잠금이
**커밋까지** 유지된다. 오늘은 운영 데이터도 배포처도 없지만, **적혀 있지 않으면
배포하는 사람이 모르고 지나간다.**

Revision ID: 361ec789023c
Revises: 992bb442d985
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "361ec789023c"
down_revision: str | None = "992bb442d985"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 결속 ① 품목이 자기 자재군을 외래키로 내어 줄 수 있게 한다 ───────────
    # `id` 가 이미 기본키라 행을 좁히지 않는다. 복합 외래키의 상대가 되려면 그
    # 쌍이 유일키여야 하기 때문에 둔다.
    op.create_unique_constraint("uq_item_id_material_group", "items", ["id", "material_group"])

    # ── 결속 ② 검사가 자기 품목의 자재군을 든다 ────────────────────────────
    # **널 허용으로 붙이고 채운 뒤에 조인다.** 한 번에 `NOT NULL` 로 붙이면 줄이
    # 하나라도 있는 데이터베이스에서 그 자리가 터진다.
    op.add_column(
        "inspections", sa.Column("material_group", sa.String(length=30), nullable=True)
    )
    # 값을 지어내지 않는다 — 품목이 이미 아는 것을 그대로 끌어온다.
    op.execute(
        "UPDATE inspections AS i SET material_group = it.material_group"
        " FROM items AS it WHERE it.id = i.item_id"
    )
    op.alter_column("inspections", "material_group", nullable=False)
    op.create_foreign_key(
        "fk_inspection_material_group",
        "inspections",
        "items",
        ["item_id", "material_group"],
        ["id", "material_group"],
    )
    # 측정 줄이 가리킬 상대. 여기서도 `id` 가 기본키라 행을 좁히지 않는다.
    op.create_unique_constraint(
        "uq_inspection_id_material_group", "inspections", ["id", "material_group"]
    )

    # ── 측정값 줄 ──────────────────────────────────────────────────────────
    op.create_table(
        "inspection_measurements",
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(length=30), nullable=False),
        sa.Column("process_code", sa.String(length=30), nullable=False),
        sa.Column("material_group", sa.String(length=30), nullable=False),
        sa.Column("measured_value", sa.Float(), nullable=False),
        sa.Column("applied_upper_spec", sa.Float(), nullable=True),
        sa.Column("applied_lower_spec", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "applied_lower_spec IS NULL OR (applied_lower_spec > '-Infinity'::double precision AND applied_lower_spec < 'Infinity'::double precision)",
            name="ck_inspection_measurement_lower_spec_is_finite",
        ),
        sa.CheckConstraint(
            "applied_upper_spec IS NULL OR (applied_upper_spec > '-Infinity'::double precision AND applied_upper_spec < 'Infinity'::double precision)",
            name="ck_inspection_measurement_upper_spec_is_finite",
        ),
        sa.CheckConstraint(
            "measured_value > '-Infinity'::double precision AND measured_value < 'Infinity'::double precision",
            name="ck_inspection_measurement_value",
        ),
        sa.CheckConstraint(
            "applied_upper_spec IS NOT NULL OR applied_lower_spec IS NOT NULL",
            name="ck_inspection_measurement_has_a_spec",
        ),
        sa.CheckConstraint(
            "applied_upper_spec IS NULL OR applied_lower_spec IS NULL OR applied_upper_spec > applied_lower_spec",
            name="ck_inspection_measurement_spec_order",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id", "material_group"],
            ["inspections.id", "inspections.material_group"],
            name="fk_inspection_measurement_inspection",
        ),
        sa.ForeignKeyConstraint(
            ["process_code", "item_code", "material_group"],
            [
                "process_inspection_standards.process_code",
                "process_inspection_standards.item_code",
                "process_inspection_standards.material_group",
            ],
            name="fk_inspection_measurement_standard",
        ),
        sa.PrimaryKeyConstraint("inspection_id", "item_code"),
    )


def downgrade() -> None:
    # **사라지는 것을 먼저 말하고 멈춘다.** 측정값은 판정의 근거이고, 그때 쓴
    # 규격이 함께 박혀 있어 기준 표에서 다시 만들 수 없다.
    #
    # **판정자의 이름은 싣지 않는다** — 형제 리비전 `992bb442d985` 가 그 이유를
    # 적는다(감사 ⑲ NC-173). 수와 찾아갈 자리로 대신한다.
    #
    # **앞선 리비전의 가드가 이 자리를 대신하지 못한다.** `08d406fa7f3b` 는
    # 로트를 세므로 로트를 만들지 않는 판정(불합격)의 측정값을 보지 못한다.
    op.execute(
        """
        DO $$
        DECLARE measured bigint; judges bigint;
        BEGIN
          SELECT count(*), count(DISTINCT i.judged_by) INTO measured, judges
          FROM inspections AS i JOIN inspection_measurements AS m ON m.inspection_id = i.id;
          IF measured > 0 THEN
            RAISE EXCEPTION
              '되돌리면 측정값과 그때 쓴 규격이 사라진다 — 잰 줄 %개 · 판정자 %명. 누구인지는 SELECT DISTINCT judged_by FROM inspections 가 말한다. 판정의 근거라 기준 표에서 다시 만들 수 없다',
              measured, judges;
          END IF;
        END $$;
        """
    )

    # **올린 것의 역순이다.** 가리키는 쪽을 먼저 떼지 않으면 가리켜지는 쪽을
    # 지울 수 없다 — 자동 생성은 `items` 의 유일키부터 떼려 했고, 그것을
    # 가리키는 외래키가 아직 `inspections` 에 붙어 있다.
    op.drop_table("inspection_measurements")
    op.drop_constraint("uq_inspection_id_material_group", "inspections", type_="unique")
    op.drop_constraint("fk_inspection_material_group", "inspections", type_="foreignkey")
    op.drop_column("inspections", "material_group")
    op.drop_constraint("uq_item_id_material_group", "items", type_="unique")
