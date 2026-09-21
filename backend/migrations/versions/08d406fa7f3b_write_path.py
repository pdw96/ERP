"""로트가 자기를 만든 검사를 가리킨다 — 불합격은 재고가 되지 않는다

표를 세우지 않는다. `lots` 에 칸 둘과 제약을, `inspections` 에 유일키 하나를
붙여 **원칙 ① 을 제약으로 만든다.**

- `lots.inspection_id` — 특채 표식을 **칸이 아니라 구조로** 둔다. 로트가 자기를
  만든 검사를 가리키면 특채 여부도 판정자도 측정값도 검사 쪽에 한 번만 산다
- `lots.inspection_result` — 「불합격이 로트를 만들지 못한다」는 **다른 표의 칸을
  보는 조건**이라 CHECK 로 적을 수 없다. 판정을 이 줄에 들고 쌍으로 가리키면
  그 줄만 보고 막을 수 있다. 값을 나르는 칸이 아니라 외래키의 자리다

**자동 생성을 그대로 쓰지 않았다. CHECK 가 통째로 빠져 있었다** — Alembic 은
기존 표에 붙는 CHECK 를 감지하지 않는다(`65d31f8b7918` 에서 넷이 같은 이유로
빠졌다). 손으로 적었고 `tests/test_migrations.py` 가 두 스키마를 견준다.

**올릴 때 멈추지 않는다 — 한 번 멈추게 했다가 되돌렸다.** 처음에는 「사 온 로트에는
검사가 있다」를 양방향 CHECK 로 걸고, 그것을 만족할 수 없는 옛 줄을 이름으로 말하고
멈추게 했다. **그 제약이 기초재고를 막았다** — 과거를 소급하지 않기로 했으므로 이월로
깔리는 자재 로트에는 적을 검사가 없고, 그것은 이미 선 사실이다. 「제약이 사실을 막으면
안 된다」가 그 테스트의 말이고, 맞는 쪽은 테스트였다.

그래서 이 리비전은 **검사를 가리키는 로트만** 판정에 묶고, **올릴 때 아무것도
멈추지 않는다** — 옛 자재 로트는 검사를 모르는 채로 그대로 선다. 가리키지 않는
자재 로트를 「이월」과 「건너뛴 것」으로 가르려면 이월을 표시할 자리가 있어야 하고,
그 자리는 전기이월이 서는 조각의 것이다.

> **가드도 함께 빠졌다.** CHECK 를 되돌릴 때 그것 때문에 멈추던 가드가 남아
> 있었고, 막을 것이 없는데 멈추고 있었다 —
> `tests/test_migrations.py::test_upgrade_does_not_stop_for_a_lot_that_came_before`
> 가 그것을 잡았다. **빼는 것도 전수해야 한다**는 것이 이 자리의 입력이다.

**내릴 때도 멈춘다.** 칸 둘을 지우면 **어느 판정이 그 로트를 만들었는지**가
사라지고 복구할 방법이 없다. 되돌리기가 사람이 남긴 것을 조용히 지우는 자리는
이 저장소에서 여섯 번 나왔다(NC-8 · 9 · 13 · 17 · 23 · 62) — 일곱 번째로 만들지
않는다. 가리키는 로트가 하나도 없을 때만 조용히 내려간다.

> **W-6 의 입력이 하나 는다.** 이번에도 「이 리비전이 만들지 않은 것은 되돌릴 때
> 건드리지 않는다」를 **손으로** 적었다. 다만 이 리비전의 가드는 앞의 것들과 축이
> 다르다 — 앞의 것들은 「그 줄의 어떤 칸이 사람의 것인가」를 물었고, 여기서는
> **칸 자체가 이 리비전의 것인데 그 안의 값이 사람의 것**이다.

**올릴 때 잠근다.** `inspections` 와 `lots` 의 유일키가 각각 인덱스를 만들고,
CHECK 둘이 기존 행 전체를 검사하며, `stock_ledger_entries` 의 외래키 둘을 떼고
하나로 다시 건다 — **외래키는 양쪽을 잡으므로** 이 리비전의 외래키가 가리키는
표는 전부 함께 잠기고 그동안 쓰기가 멈춘다(목록을 세지 않는다. 세면 갈린다).
`migrations/env.py` 가 전체를 트랜잭션 하나로 감싸므로 커밋까지 유지된다.

Revision ID: 08d406fa7f3b
Revises: e84fbec436c0
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "08d406fa7f3b"
down_revision: str | None = "e84fbec436c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_inspection_id_result", "inspections", ["id", "result"])
    op.add_column("lots", sa.Column("inspection_id", sa.Integer(), nullable=True))
    op.add_column("lots", sa.Column("inspection_result", sa.String(length=10), nullable=True))
    op.create_unique_constraint("uq_lot_inspection", "lots", ["inspection_id"])
    op.create_unique_constraint("uq_lot_id_inspection", "lots", ["id", "inspection_id"])
    op.create_foreign_key(
        "fk_lot_inspection",
        "lots",
        "inspections",
        ["inspection_id", "inspection_result"],
        ["id", "result"],
    )
    # **원장의 입고 줄이 「그 로트를 만든 검사」를 가리키게 묶는다.** 표 18 이
    # 설 때는 로트가 검사를 몰라 이 쌍을 만들 수 없었고, 그래서 미결로 들어 두었던
    # 자리다. 둘을 따로 가리키면 둘 다 실재한다는 것까지만 증명된다.
    op.drop_constraint("fk_stock_ledger_entry_lot", "stock_ledger_entries", type_="foreignkey")
    op.drop_constraint(
        "fk_stock_ledger_entry_inspection", "stock_ledger_entries", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_lot",
        "stock_ledger_entries",
        "lots",
        ["lot_id", "inspection_id"],
        ["id", "inspection_id"],
    )
    op.create_check_constraint(
        "ck_lot_inspection_result_matches_inspection",
        "lots",
        "(inspection_id IS NULL) = (inspection_result IS NULL)",
    )
    op.create_check_constraint(
        "ck_lot_is_not_from_a_failed_inspection",
        "lots",
        "inspection_result IS DISTINCT FROM '불합격'",
    )


def downgrade() -> None:
    # **사라지는 것을 먼저 이름으로 말하고 멈춘다.** 칸 둘을 지우면 어느 판정이
    # 그 로트를 만들었는지가 사라지고, 특채로 들어온 로트는 표식까지 잃는다.
    op.execute(
        """
        DO $$
        DECLARE judged text;
        BEGIN
          SELECT string_agg(lot_number, ', ' ORDER BY lot_number) INTO judged
          FROM lots WHERE inspection_id IS NOT NULL;
          IF judged IS NOT NULL THEN
            RAISE EXCEPTION
              '되돌리면 이 로트들이 자기를 만든 판정을 잃는다: %. 특채로 들어온 로트는 표식도 함께 사라진다',
              judged;
          END IF;
        END $$;
        """
    )

    op.drop_constraint("ck_lot_is_not_from_a_failed_inspection", "lots", type_="check")
    op.drop_constraint("ck_lot_inspection_result_matches_inspection", "lots", type_="check")
    op.drop_constraint("fk_stock_ledger_entry_lot", "stock_ledger_entries", type_="foreignkey")
    op.create_foreign_key(
        "fk_stock_ledger_entry_lot", "stock_ledger_entries", "lots", ["lot_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_inspection",
        "stock_ledger_entries",
        "inspections",
        ["inspection_id"],
        ["id"],
    )
    op.drop_constraint("fk_lot_inspection", "lots", type_="foreignkey")
    op.drop_constraint("uq_lot_id_inspection", "lots", type_="unique")
    op.drop_constraint("uq_lot_inspection", "lots", type_="unique")
    op.drop_column("lots", "inspection_result")
    op.drop_column("lots", "inspection_id")
    op.drop_constraint("uq_inspection_id_result", "inspections", type_="unique")
