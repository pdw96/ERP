"""원장 줄의 창고 — 줄마다 창고와 품목 유형을 적는다 (4단계, ADR 0022)

원장 줄에 `warehouse` · `item_type` 이 선다. 창고는 그 줄이 일어난 자리이고, 유형은 값을 나르는
칸이 아니라 외래키의 자리다 — `(lot_id, item_type) → lots (id, item_type)` 로 로트에서 끌어와
「창고가 담는 품목 유형」을 줄에서 묻는다. 대상 유일키 `uq_lot_id_item_type` 를 `lots` 에 더한다.
구매입고 · 구매반품출고 줄은 원재료창고에만 선다(`codes.LEDGER_TYPE_WAREHOUSES`).

**트리거 둘이 바뀐다** — 글자는 `app/db/ledger_guards.py` 와 같다. 잔량 트리거
(`stock_ledger_entry_keeps_the_balance`)가 입고 줄의 창고를 로트의 들어온 창고와 견주고, 새
트리거(`lot_warehouse_stays_with_its_ledger`)가 원장에 줄이 선 로트의 `warehouse` 를 굳힌다.
잔량은 아직 로트 하나로 센다 — 창고별 잔량과 나뉜 로트의 폐기는 이동이 서는 조각의 일이다
(저장소 소유자, 2026-10-05).

**옛 줄을 채운다 — 지어내지 않는다.** 옛 줄의 창고와 유형은 그 로트의 `lots.warehouse` ·
`lots.item_type` 이다. 칸을 비워 둔 채 더하고, 채운 뒤에 `NOT NULL` 로 조이고, 그 뒤에 제약을
건다 — 처음부터 `NOT NULL` 이면 줄이 있는 데이터베이스에서 리비전이 멈추고, 비운 채 제약을
걸면 `NULL` 이 복합 외래키와 CHECK 를 함께 지난다(PR #98 Codex 리뷰).

**올릴 때 묻는다 — 원재료창고가 아닌 로트에 선 원장 줄.** 앞 스키마는 원자재 로트를 생산창고에도
세울 수 있었다. 그런 로트의 입고 줄을 채우면 「구매입고는 원재료창고」 CHECK 가 제약 이름만 내놓고
멈춘다 — 가드가 먼저 로트 번호를 말하고 멈춘다. 유형 쪽은 따로 묻지 않는다 — 채우는 값은 로트가
이미 품목과 쌍 외래키로 맞춘 유형이고, 「창고가 담는 품목 유형」은 `lots` 의 같은 CHECK 를 지난
쌍을 그대로 옮긴 것이다.

**내릴 때도 묻는다 — 로트의 들어온 창고와 다른 창고에 선 줄.** 칸을 지우면 그 줄이 어느 창고에서
일어났는지가 사라진다. 로트의 창고와 같은 줄은 다시 채울 수 있으므로 조용히 내려가고, 다른 줄이
하나라도 있으면 몇 건인지 말하고 멈춘다(W-6 ①). **세기 전에 잠근다** — 줄을 넣는 트랜잭션이
커밋되기 전에 세면 0 을 보고 지나간다.

**올릴 때 잠근다.** 칸을 더하고 채우는 원장과 유일키를 받는 `lots` 에 ACCESS EXCLUSIVE 가 커밋까지
남는다 — 읽기까지 멈춘다. 채우는 `UPDATE` · `SET NOT NULL` · CHECK · 외래키가 옛 줄 전부를 지나므로
잠금의 길이는 원장의 행 수가 정한다. `migrations/env.py` 가 전체를 트랜잭션 하나로 감싼다.

Revision ID: 1e5667151a9f
Revises: 53bd4c97a00e
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1e5667151a9f"
down_revision: str | None = "53bd4c97a00e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── 트리거 — `app/db/ledger_guards.py` 와 같은 글자 ─────────────────────────

_LEDGER_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_ledger_entry_keeps_the_balance() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_quantity double precision;
  lot_warehouse text;
  lot_label text;
  effect text;
  expected text;
  came_in timestamp;
  balance numeric;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION '원장 줄은 고치거나 지우지 않는다 — 취소는 반대 방향의 새 줄이다 (줄 %)',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  IF NOT (NEW.quantity > '-Infinity' AND NEW.quantity < 'Infinity') THEN
    RETURN NEW;
  END IF;

  SELECT quantity, warehouse, lot_number INTO lot_quantity, lot_warehouse, lot_label
  FROM lots WHERE id = NEW.lot_id FOR NO KEY UPDATE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  IF NEW.txn_type = '구매입고'
     AND NEW.quantity IS DISTINCT FROM lot_quantity THEN
    RAISE EXCEPTION '입고 줄의 수량(%)이 로트 %의 수량(%)과 다르다',
      NEW.quantity, lot_label, lot_quantity
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type = '구매입고'
     AND NEW.warehouse IS DISTINCT FROM lot_warehouse THEN
    RAISE EXCEPTION '입고 줄의 창고(%)가 로트 %의 들어온 창고(%)와 다르다',
      NEW.warehouse, lot_label, lot_warehouse
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT total_effect INTO effect FROM txn_type_attributes
  WHERE group_code = NEW.txn_type_group AND code = NEW.txn_type FOR SHARE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;
  expected := CASE NEW.txn_type WHEN '구매입고' THEN '증가' WHEN '구매반품출고' THEN '감소' WHEN '폐기출고' THEN '감소' END;
  IF expected IS NULL THEN
    RETURN NEW;
  END IF;
  IF effect IS DISTINCT FROM expected THEN
    RAISE EXCEPTION '유형 %의 총량 영향이 「%」로 서 있다 — 원장은 이 유형을 「%」으로 센다',
      NEW.txn_type, effect, expected
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type <> '구매입고' THEN
    SELECT occurred_at INTO came_in FROM stock_ledger_entries
    WHERE lot_id = NEW.lot_id AND txn_type = '구매입고';
    IF NEW.occurred_at < came_in THEN
      RAISE EXCEPTION
        '줄의 시각(%)이 로트 %의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
        NEW.occurred_at, lot_label, came_in
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;

  SELECT coalesce(sum(CASE a.total_effect
                        WHEN '증가' THEN e.quantity::numeric
                        WHEN '감소' THEN -e.quantity::numeric
                      END), 0)
    INTO balance
  FROM stock_ledger_entries AS e
  JOIN txn_type_attributes AS a ON a.group_code = e.txn_type_group AND a.code = e.txn_type
  WHERE e.lot_id = NEW.lot_id;

  IF effect = '증가' THEN
    balance := balance + NEW.quantity::numeric;
  ELSE
    balance := balance - NEW.quantity::numeric;
  END IF;

  IF balance < 0 THEN
    RAISE EXCEPTION '로트 %의 잔량이 %이 된다 — 있는 것보다 많이 뺄 수 없다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type = '폐기출고' AND balance <> 0 THEN
    RAISE EXCEPTION '폐기출고는 로트 %의 잔량 전부다 — %이 남는다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_LOT_WAREHOUSE_FUNCTION = """
CREATE OR REPLACE FUNCTION lot_warehouse_stays_with_its_ledger() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.warehouse IS DISTINCT FROM OLD.warehouse
     AND EXISTS (SELECT 1 FROM stock_ledger_entries WHERE lot_id = OLD.id) THEN
    RAISE EXCEPTION
      '로트 %의 들어온 창고는 원장에 줄이 선 뒤에 고치지 않는다 — 입고 줄과 갈린다',
      OLD.lot_number
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_LOT_WAREHOUSE_TRIGGER = """
CREATE TRIGGER lot_warehouse_stays_with_its_ledger
BEFORE UPDATE OF warehouse ON lots
FOR EACH ROW EXECUTE FUNCTION lot_warehouse_stays_with_its_ledger()
"""

# 앞 리비전(`53bd4c97a00e`)의 글자 — 내릴 때 되돌린다.
_LEDGER_GUARD_FUNCTION_BEFORE = """
CREATE OR REPLACE FUNCTION stock_ledger_entry_keeps_the_balance() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_quantity double precision;
  lot_label text;
  effect text;
  expected text;
  came_in timestamp;
  balance numeric;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION '원장 줄은 고치거나 지우지 않는다 — 취소는 반대 방향의 새 줄이다 (줄 %)',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  IF NOT (NEW.quantity > '-Infinity' AND NEW.quantity < 'Infinity') THEN
    RETURN NEW;
  END IF;

  SELECT quantity, lot_number INTO lot_quantity, lot_label
  FROM lots WHERE id = NEW.lot_id FOR NO KEY UPDATE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  IF NEW.txn_type = '구매입고'
     AND NEW.quantity IS DISTINCT FROM lot_quantity THEN
    RAISE EXCEPTION '입고 줄의 수량(%)이 로트 %의 수량(%)과 다르다',
      NEW.quantity, lot_label, lot_quantity
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT total_effect INTO effect FROM txn_type_attributes
  WHERE group_code = NEW.txn_type_group AND code = NEW.txn_type FOR SHARE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;
  expected := CASE NEW.txn_type WHEN '구매입고' THEN '증가' WHEN '구매반품출고' THEN '감소' WHEN '폐기출고' THEN '감소' END;
  IF expected IS NULL THEN
    RETURN NEW;
  END IF;
  IF effect IS DISTINCT FROM expected THEN
    RAISE EXCEPTION '유형 %의 총량 영향이 「%」로 서 있다 — 원장은 이 유형을 「%」으로 센다',
      NEW.txn_type, effect, expected
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type <> '구매입고' THEN
    SELECT occurred_at INTO came_in FROM stock_ledger_entries
    WHERE lot_id = NEW.lot_id AND txn_type = '구매입고';
    IF NEW.occurred_at < came_in THEN
      RAISE EXCEPTION
        '줄의 시각(%)이 로트 %의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
        NEW.occurred_at, lot_label, came_in
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;

  SELECT coalesce(sum(CASE a.total_effect
                        WHEN '증가' THEN e.quantity::numeric
                        WHEN '감소' THEN -e.quantity::numeric
                      END), 0)
    INTO balance
  FROM stock_ledger_entries AS e
  JOIN txn_type_attributes AS a ON a.group_code = e.txn_type_group AND a.code = e.txn_type
  WHERE e.lot_id = NEW.lot_id;

  IF effect = '증가' THEN
    balance := balance + NEW.quantity::numeric;
  ELSE
    balance := balance - NEW.quantity::numeric;
  END IF;

  IF balance < 0 THEN
    RAISE EXCEPTION '로트 %의 잔량이 %이 된다 — 있는 것보다 많이 뺄 수 없다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type = '폐기출고' AND balance <> 0 THEN
    RAISE EXCEPTION '폐기출고는 로트 %의 잔량 전부다 — %이 남는다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""


def upgrade() -> None:
    op.add_column("stock_ledger_entries", sa.Column("warehouse", sa.String(20), nullable=True))
    op.add_column("stock_ledger_entries", sa.Column("item_type", sa.String(20), nullable=True))

    # **조이기 전에 묻는다.** 옛 줄의 창고는 그 로트의 들어온 창고로 채우는데, 원재료창고가 아닌
    # 로트에 선 줄은 아래의 「유형이 창고를 정한다」 CHECK 가 제약 이름만 내놓고 멈춘다 — 어느
    # 로트 때문인지 말하고 먼저 멈춘다.
    op.execute(
        """
        DO $$
        DECLARE misplaced text;
        BEGIN
          SELECT string_agg(DISTINCT l.lot_number, ', ' ORDER BY l.lot_number) INTO misplaced
          FROM stock_ledger_entries AS e
          JOIN lots AS l ON l.id = e.lot_id
          WHERE l.warehouse <> '원재료';
          IF misplaced IS NOT NULL THEN
            RAISE EXCEPTION
              '원재료창고가 아닌 로트에 원장 줄이 있다: %. 3단계까지의 줄은 사 온 물건의 것이라 원재료창고에서 났어야 하므로 사람이 먼저 가른다',
              misplaced;
          END IF;
        END $$;
        """
    )
    # **채우는 동안만 잔량 트리거를 끈다.** 그 트리거는 원장 줄의 `UPDATE` 를 전부 거부한다 —
    # 사람이 일어난 일을 고치는 길을 막는 것이고, 그것이 맞다. 여기서 쓰는 것은 이 리비전이 방금
    # 세운 빈 칸뿐이고 옛 줄의 사실(로트 · 유형 · 수량 · 시각)은 그대로다. 그사이 다른 쓰기가
    # 트리거 없이 끼지 못하는 것은 위에서 칸을 더한 `ADD COLUMN` 이 ACCESS EXCLUSIVE 를 커밋까지
    # 쥐고 있어서다 — 트리거를 끄는 문장 자신은 SHARE ROW EXCLUSIVE 만 잡는다. 리비전 전체가 한
    # 트랜잭션이라 중간에 멈추면 끈 것도 함께 되돌아간다.
    op.execute(
        "ALTER TABLE stock_ledger_entries DISABLE TRIGGER stock_ledger_entry_keeps_the_balance"
    )
    op.execute(
        """
        UPDATE stock_ledger_entries AS e
        SET warehouse = l.warehouse, item_type = l.item_type
        FROM lots AS l
        WHERE l.id = e.lot_id
        """
    )
    op.execute(
        "ALTER TABLE stock_ledger_entries ENABLE TRIGGER stock_ledger_entry_keeps_the_balance"
    )
    op.alter_column(
        "stock_ledger_entries", "warehouse", existing_type=sa.String(20), nullable=False
    )
    op.alter_column(
        "stock_ledger_entries", "item_type", existing_type=sa.String(20), nullable=False
    )

    op.create_unique_constraint("uq_lot_id_item_type", "lots", ["id", "item_type"])
    op.create_check_constraint(
        "ck_stock_ledger_entry_warehouse",
        "stock_ledger_entries",
        "warehouse IN ('원재료', '생산', '제품')",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_warehouse_holds_type",
        "stock_ledger_entries",
        "(warehouse = '원재료' AND item_type IN ('원자재')) OR (warehouse = '생산' AND item_type IN ('원자재', '반제품', '완제품')) OR (warehouse = '제품' AND item_type IN ('완제품'))",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse",
        "stock_ledger_entries",
        "(txn_type <> '구매입고' OR warehouse = '원재료') AND (txn_type <> '구매반품출고' OR warehouse = '원재료')",
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_lot_type",
        "stock_ledger_entries",
        "lots",
        ["lot_id", "item_type"],
        ["id", "item_type"],
    )

    for statement in (_LEDGER_GUARD_FUNCTION, _LOT_WAREHOUSE_FUNCTION, _LOT_WAREHOUSE_TRIGGER):
        op.execute(statement)


def downgrade() -> None:
    # **세기 전에 잠근다** — 원장 줄을 넣는 트랜잭션이 커밋되기 전에 세면 0 을 보고 지나간다.
    op.execute("LOCK TABLE stock_ledger_entries IN SHARE MODE")
    op.execute(
        """
        DO $$
        DECLARE elsewhere bigint;
        BEGIN
          SELECT count(*) INTO elsewhere
          FROM stock_ledger_entries AS e
          JOIN lots AS l ON l.id = e.lot_id
          WHERE e.warehouse <> l.warehouse;
          IF elsewhere > 0 THEN
            RAISE EXCEPTION
              '되돌리면 로트의 들어온 창고와 다른 창고에 선 원장 줄 %건이 어디서 일어났는지 잃는다',
              elsewhere;
          END IF;
        END $$;
        """
    )

    op.execute("DROP TRIGGER lot_warehouse_stays_with_its_ledger ON lots")
    op.execute("DROP FUNCTION lot_warehouse_stays_with_its_ledger()")
    op.execute(_LEDGER_GUARD_FUNCTION_BEFORE)

    op.drop_constraint(
        "fk_stock_ledger_entry_lot_type", "stock_ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse", "stock_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_warehouse_holds_type", "stock_ledger_entries", type_="check"
    )
    op.drop_constraint("ck_stock_ledger_entry_warehouse", "stock_ledger_entries", type_="check")
    op.drop_constraint("uq_lot_id_item_type", "lots", type_="unique")
    op.drop_column("stock_ledger_entries", "item_type")
    op.drop_column("stock_ledger_entries", "warehouse")
