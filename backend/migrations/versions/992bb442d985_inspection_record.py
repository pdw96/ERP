"""검사 기록 — 합격이 로트를 만드는 자리

표 하나(`inspections`)를 세우고, 기존 표 하나(`nonconformity_stage_rules`)에
유일키를 더한다. 그 유일키는 행을 좁히지 않는다 — **검사 기록의 복합 외래키가
가리킬 상대**를 만드는 것이 목적이다.

**자동 생성이 이번에는 CHECK 를 빠뜨리지 않았다.** 표를 새로 만드는 리비전이라
`create_table` 이 모델의 `__table_args__` 를 그대로 굽기 때문이다 — 칸을 **더하는**
리비전이었던 `65d31f8b7918` 에서 넷이 통째로 빠졌던 것과 다른 자리다. 그래도
`pytest tests/test_migrations.py` 를 돌려 두 스키마를 견주고 나서 믿는다.

**퍼센트가 없다.** `LIKE 'FG-%'` 를 굽지 않으므로 초기 리비전에서 손으로 되돌려야
했던 그 자리가 이번에는 나지 않는다.

**데이터 단계가 없다.** 검사 기록은 거래 표라서 비어서 서는 것이 정상이고, 더한
유일키는 기존 기본키의 상위 집합이라 이미 심긴 줄이 위반할 수 없다.

**`downgrade()` 가 검사 기록을 통째로 지운다. 그래서 멈추고 이름을 말한다.**
처음에는 멈추지 않았고 그 이유를 「이 리비전이 세운 표라 그 안의 모든 줄이 이
리비전 뒤에 생긴 것이고, 「사람이 먼저 넣어 둔 값」이 있을 수 없다」고 적었다 —
**명제는 참이고 함의가 거짓이다.** 이 저장소가 여섯 번 물어 온 것은 「먼저
넣었는가」가 아니라 **「그 줄을 이 리비전이 만들었는가」**이고, `create_table` 은
줄을 하나도 만들지 않는다. 표는 이 리비전의 것이고 **줄은 사람의 판정**이다.

**`08d406fa7f3b` 의 가드가 이 자리를 대신하지 못한다.** 그쪽은 검사를 가리키는
**로트**를 세므로 **로트를 만들지 않는 판정 — 불합격 — 을 구조적으로 보지 못한다.**
하필 불합격은 로트에도 원장에도 사본이 없어 **이 표에만 사는 사실**이다.

**올릴 때 잠근다.** 유일키는 `nonconformity_stage_rules` 에 `AccessExclusiveLock`
을 잡고 인덱스를 만든다 — `CONCURRENTLY` 를 쓸 수 없는 형태다. 그리고 **이
`CREATE TABLE` 의 외래키가 가리키는 표는 전부 함께 잠긴다** — 외래키는 양쪽을
잡으므로 그 표들의 쓰기도 그동안 멈춘다(목록을 세지 않는다. 세면 갈린다).
`migrations/env.py` 가 전체를 트랜잭션 하나로 감싸므로 커밋까지 유지된다. 오늘은
운영 데이터도 배포처도 없지만, **적혀 있지 않으면 배포하는 사람이 모르고 지나간다.**

Revision ID: 992bb442d985
Revises: 65d31f8b7918
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "992bb442d985"
down_revision: str | None = "65d31f8b7918"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # **특채를 여는 것은 이 유일키다.** 검사 기록이 `(사유 × 단계 × 플래그)` 로
    # 이 표를 가리키려면 그 넷이 기본키나 유일키여야 한다. 앞의 네 칸은 이미
    # 기본키이므로 행이 더 좁아지지는 않는다.
    op.create_unique_constraint(
        "uq_nonconformity_stage_rule_special_acceptance",
        "nonconformity_stage_rules",
        [
            "reason_group",
            "reason_code",
            "stage_group",
            "stage_code",
            "special_acceptance_allowed",
        ],
    )
    op.create_table(
        "inspections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "inspection_stage", sa.String(length=20), server_default="IQC", nullable=False
        ),
        sa.Column(
            "stage_group", sa.String(length=20), server_default="INSP_STAGE", nullable=False
        ),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=20), server_default="원자재", nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column(
            "supplier_type", sa.String(length=10), server_default="공급사", nullable=False
        ),
        sa.Column("supplier_lot_number", sa.String(length=50), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("judged_at", sa.DateTime(), nullable=False),
        sa.Column("judged_by", sa.String(length=50), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("nonconformity_code", sa.String(length=30), nullable=True),
        sa.Column(
            "nonconformity_group",
            sa.String(length=20),
            server_default="NC_REASON",
            nullable=False,
        ),
        sa.Column("special_acceptance_allowed", sa.Boolean(), nullable=True),
        sa.CheckConstraint(
            "(result = '특채') = (special_acceptance_allowed IS NOT NULL)",
            name="ck_inspection_special_acceptance_matches_result",
        ),
        sa.CheckConstraint(
            "(result = '합격') = (nonconformity_code IS NULL)",
            name="ck_inspection_reason_matches_result",
        ),
        sa.CheckConstraint(
            "btrim(judged_by, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_inspection_judged_by_is_present",
        ),
        sa.CheckConstraint(
            "btrim(supplier_lot_number, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_inspection_supplier_lot_number_is_present",
        ),
        sa.CheckConstraint("inspection_stage = 'IQC'", name="ck_inspection_stage_is_incoming"),
        sa.CheckConstraint("item_type = '원자재'", name="ck_inspection_item_is_raw_material"),
        sa.CheckConstraint(
            "nonconformity_group = 'NC_REASON'", name="ck_inspection_nonconformity_group"
        ),
        sa.CheckConstraint(
            "quantity >= 0 AND quantity > '-Infinity'::double precision AND quantity < 'Infinity'::double precision",
            name="ck_inspection_quantity",
        ),
        sa.CheckConstraint("result IN ('합격', '불합격', '특채')", name="ck_inspection_result"),
        sa.CheckConstraint("stage_group = 'INSP_STAGE'", name="ck_inspection_stage_group"),
        sa.CheckConstraint("supplier_type = '공급사'", name="ck_inspection_is_supplier"),
        sa.CheckConstraint(
            "special_acceptance_allowed IS NOT FALSE",
            name="ck_inspection_special_acceptance_is_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "item_type"],
            ["items.id", "items.item_type"],
            name="fk_inspection_item",
        ),
        sa.ForeignKeyConstraint(
            [
                "nonconformity_group",
                "nonconformity_code",
                "stage_group",
                "inspection_stage",
                "special_acceptance_allowed",
            ],
            [
                "nonconformity_stage_rules.reason_group",
                "nonconformity_stage_rules.reason_code",
                "nonconformity_stage_rules.stage_group",
                "nonconformity_stage_rules.stage_code",
                "nonconformity_stage_rules.special_acceptance_allowed",
            ],
            name="fk_inspection_special_acceptance",
        ),
        sa.ForeignKeyConstraint(
            ["nonconformity_group", "nonconformity_code", "stage_group", "inspection_stage"],
            [
                "nonconformity_stage_rules.reason_group",
                "nonconformity_stage_rules.reason_code",
                "nonconformity_stage_rules.stage_group",
                "nonconformity_stage_rules.stage_code",
            ],
            name="fk_inspection_nonconformity",
        ),
        sa.ForeignKeyConstraint(
            ["stage_group", "inspection_stage"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_inspection_stage",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id", "supplier_type"],
            ["partners.id", "partners.partner_type"],
            name="fk_inspection_supplier",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # **사라지는 것을 먼저 말하고 멈춘다.** 표는 이 리비전의 것이지만 줄은
    # 사람의 판정이다.
    #
    # **판정자의 이름을 싣지 않는다** (감사 ⑲ NC-173). 한때 명단을
    # `string_agg(DISTINCT judged_by)` 로 실었는데, `RAISE EXCEPTION` 의
    # 메시지는 되돌리는 사람의 터미널뿐 아니라 **PostgreSQL 서버 로그 파일**에도
    # 간다(찍어서 확인했다) — 표와 보존 기간도 읽는 사람도 다른 자리다. 같은 값을
    # 앱 층에서는 이미 껐으므로(NC-164) 여기만 열려 있었다. 수와 **찾아갈 자리**를
    # 적으면 멈추는 힘도 사람이 물어볼 대상을 아는 것도 그대로 남고 **명단의
    # 사본만 사라진다.**
    #
    # 가드가 **보지 못하는 부류**: 이것은 세기만 하고 **무엇을 판정했는지는 말하지
    # 않는다.** 정말 버릴 때는 사람이 손으로 비우고 다시 내린다.
    op.execute(
        """
        DO $$
        DECLARE judgements bigint; judges bigint;
        BEGIN
          SELECT count(*), count(DISTINCT judged_by) INTO judgements, judges FROM inspections;
          IF judgements > 0 THEN
            RAISE EXCEPTION
              '되돌리면 검사 기록이 통째로 사라진다 — 판정 %건 · 판정자 %명. 누구인지는 SELECT DISTINCT judged_by FROM inspections 가 말한다. 불합격 판정은 이 표에만 살아 로트에도 원장에도 사본이 없다',
              judgements, judges;
          END IF;
        END $$;
        """
    )

    # 표가 먼저다 — 검사 기록이 유일키를 가리키고 있으므로 그것을 지우기 전에는
    # 유일키를 떼지 못한다.
    op.drop_table("inspections")
    op.drop_constraint(
        "uq_nonconformity_stage_rule_special_acceptance",
        "nonconformity_stage_rules",
        type_="unique",
    )
