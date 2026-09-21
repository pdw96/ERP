"""수불 원장 — 로트가 생기고 움직인 사실

표 하나(`stock_ledger_entries`)를 세운다. 앞의 두 리비전과 달리 **기존 표를
건드리지 않는다** — 결속이 필요 없는 것은 원장이 가리키기만 하고 가리켜지지는
않기 때문이다.

**자동 생성을 그대로 쓰지 않았다.** 처음 생성분에는 외래키 둘에 **이름이 없었다**
— 모델이 칸에 `ForeignKey(...)` 를 달았기 때문이다. 이름 없는 제약은
데이터베이스가 지어 주는 이름을 갖게 되어 나중에 떼거나 고칠 때 그 이름을 먼저
찾아야 한다. 모델을 고쳐 `__table_args__` 에서 이름을 주고 다시 생성했다.

**데이터 단계가 없다.** 원장은 거래 표라서 비어서 서는 것이 정상이다.

**부분 유일 인덱스가 하나 있다** — 로트 하나에 입고 줄은 하나다. 유형을 조건에
적어 두었으므로 불출이 서는 날에도 그대로 옳다. `UNIQUE (lot_id)` 로 두면 오늘은
같은 뜻이지만 그때 손봐야 하고, **손봐야 하는 제약은 손보지 않은 채로 남는다.**

**`downgrade()` 가 원장을 통째로 지운다.** 되돌릴 수 없다 — 들어온 사실과 그
근거가 함께 사라지고 복구할 방법은 백업뿐이다. **멈추고 이름을 말하지는 않는다**:
이 리비전이 세운 표라 그 안의 모든 줄이 이 리비전 뒤에 생긴 것이고, 「사람이 먼저
넣어 둔 값」이 있을 수 없기 때문이다.

**올릴 때 잠근다.** `CREATE TABLE` 하나와 인덱스 하나이지만, **외래키 셋이
가리켜지는 표 셋**(`lots` · `inspections` · `txn_type_attributes`)을 함께 잡는다 —
외래키는 양쪽을 잡으므로 그 셋의 쓰기도 그동안 멈춘다. `migrations/env.py` 가
전체를 트랜잭션 하나로 감싸므로 커밋까지 유지된다. 오늘은 운영 데이터도 배포처도
없지만, **적혀 있지 않으면 배포하는 사람이 모르고 지나간다.**

Revision ID: e84fbec436c0
Revises: 361ec789023c
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e84fbec436c0"
down_revision: str | None = "361ec789023c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("txn_type", sa.String(length=30), nullable=False),
        sa.Column(
            "txn_type_group", sa.String(length=20), server_default="TXN_TYPE", nullable=False
        ),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0 AND quantity > '-Infinity'::double precision AND quantity < 'Infinity'::double precision",
            name="ck_stock_ledger_entry_quantity",
        ),
        sa.CheckConstraint(
            "txn_type = '구매입고'", name="ck_stock_ledger_entry_is_a_purchase_receipt"
        ),
        sa.CheckConstraint(
            "txn_type_group = 'TXN_TYPE'", name="ck_stock_ledger_entry_txn_type_group"
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["inspections.id"], name="fk_stock_ledger_entry_inspection"
        ),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], name="fk_stock_ledger_entry_lot"),
        sa.ForeignKeyConstraint(
            ["txn_type_group", "txn_type"],
            ["txn_type_attributes.group_code", "txn_type_attributes.code"],
            name="fk_stock_ledger_entry_txn_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # **로트 하나에 입고 줄은 하나다.** 조건에 유형을 적어 두었으므로 불출이 서는
    # 날 한 로트에 여러 줄이 나도 이 제약은 그대로 옳다.
    op.create_index(
        "uq_stock_ledger_entry_one_receipt_per_lot",
        "stock_ledger_entries",
        ["lot_id"],
        unique=True,
        postgresql_where=sa.text("txn_type = '구매입고'"),
    )


def downgrade() -> None:
    # 인덱스는 표와 함께 사라지므로 따로 떼지 않는다.
    op.drop_table("stock_ledger_entries")
