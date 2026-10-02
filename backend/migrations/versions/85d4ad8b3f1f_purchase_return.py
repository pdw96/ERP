"""구매반품이 원장에 닿는다 — 반품 문서 · 반품 줄 · 잔량 트리거

표 하나(`purchase_returns`)를 세우고, 원장이 구매반품출고를 받게 넓히고, 원장의 합과 그
합이 기대는 값을 지키는 트리거를 건다(ADR 0013). 로트 수량을 그 로트를 만든 검사의 수량과
쌍으로 묶는다(감사 ㉟ NC-225). 3단계의 첫 조각이다.

**원장이 처음으로 줄어든다.** 그래서 「한 로트의 줄을 합한 잔량이 0 밑으로 내려가지
않는다」가 처음으로 깨질 수 있게 되고, 그 규칙은 여러 줄의 합이라 CHECK 로 적을 수 없다.
대장의 NC-70 이 같은 자리(로트 수량과 입고 줄 수량을 묶는 것이 코드뿐이다)를 내고 기한을
「출고가 서는 단계」로 두었는데, 이 리비전이 그 단계다.

**트리거 SQL 은 모델 쪽과 같은 글자다.** 모델은 `app/db/ledger_guards.py` 를 표가 설 때
부르고, 이 리비전은 그 글자를 여기 굳혀 둔다 — 뒤에 모델 쪽이 바뀌어도 이 리비전이 만든
것은 바뀌지 않아야 하기 때문이다. 둘이 갈리면 `tests/test_migrations.py` 가 함수와 트리거의
**정의**를 견주어 잡는다.

**올릴 때 멈출 수 있다 — 아래의 자리에서, 이름을 말하고.** 입고 줄의 수량이 로트 수량과
다른 로트가 있으면, 트리거를 거는 순간부터 그 로트는 「입고 줄과 로트가 갈린」 채로
남는다. 로트 수량이 그 로트를 만든 검사의 수량과 다른 로트도 같다 — 쌍 외래키가 먼저
걸리면 나오는 말은 제약 이름뿐이다. 앞 스키마는 둘 다 막지 않았으므로 실재할 수 있고,
**조이기 전에 묻는다.** 잔량이 음수인 로트는 물을 필요가 없다 — 이 리비전 전의 원장은
구매입고(증가) 하나만 받았다.

**올릴 때 잠근다.** `CREATE TABLE` 하나가 외래키로 가리키는 표(`inspections` · `lots` ·
`common_codes` · `nonconformity_stage_rules`)를, 원장에 붙는 외래키 · CHECK · 인덱스가 원장과
반품 문서를, 검사의 유일키와 로트의 쌍 외래키가 `inspections` 와 `lots` 를, 트리거가 그것이
걸리는 표(원장 · `lots` · `txn_type_attributes` · `purchase_returns` · `inspections`)를 잡는다
(목록을 세지 않는다. 세면 갈린다). `ADD COLUMN` 이 원장의 첫 구문이라
ACCESS EXCLUSIVE 가 커밋까지 유지되고, 그 사이 원장의 쓰기가 멈춘다. `migrations/env.py` 가
전체를 트랜잭션 하나로 감싼다.

**내릴 때 멈출 수 있다 — 반품 문서가 하나라도 있으면.** 이 리비전은 구조만 세우므로
사라지는 것은 사람이 나중에 넣은 반품뿐이고, 그것은 **다시 만들 수 없다** — 무엇을 왜
돌려보냈는지는 이 표에만 있다. 원장의 반품 줄은 문서 없이 설 수 없으므로(외래키) 문서를
세면 둘 다 센다(W-6 ①).

**내릴 때도 잠근다**(감사 ㉟ NC-224). `DROP TRIGGER` 는 그 트리거가 걸린 표에 ACCESS
EXCLUSIVE 를 잡는다 — `lots` · `inspections` · `txn_type_attributes` 의 **읽기까지** 커밋까지
멈춘다. 원장 쪽은 CHECK 를 다시 세우며 모든 줄을 다시 검증하고, 칸 · 제약 · 인덱스를 떼며 같은
잠금을 잡는다. 올릴 때보다 무겁다.

> **이 가드들이 못 보는 부류**(W-6 ③): 올릴 때의 가드는 **입고 줄이 있는 로트**만 본다 —
> 입고 줄이 없는 로트(기초재고 · 쓰기 경로가 깨진 자리)의 수량은 견줄 짝이 없다. 내릴 때의
> 가드는 반품 문서를 세므로, 문서 없이 원장에 직접 넣은 줄은 볼 수 없는데 그런 줄은 이
> 리비전의 외래키가 서는 동안 설 수 없다.

Revision ID: 85d4ad8b3f1f
Revises: b41d7c8e5a92
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "85d4ad8b3f1f"
down_revision: str | None = "b41d7c8e5a92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── 트리거 — `app/db/ledger_guards.py` 와 같은 글자 ─────────────────────────

_LEDGER_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_ledger_entry_keeps_the_balance() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_quantity double precision;
  lot_label text;
  effect text;
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
  IF effect NOT IN ('증가', '감소') THEN
    RAISE EXCEPTION '총량 영향이 「%」인 유형(%)은 잔량을 셀 수 없다', effect, NEW.txn_type
      USING ERRCODE = 'check_violation';
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

  RETURN NEW;
END $$
"""

_LEDGER_GUARD_TRIGGER = """
CREATE TRIGGER stock_ledger_entry_keeps_the_balance
BEFORE INSERT OR UPDATE OR DELETE ON stock_ledger_entries
FOR EACH ROW EXECUTE FUNCTION stock_ledger_entry_keeps_the_balance()
"""

_LOT_QUANTITY_FUNCTION = """
CREATE OR REPLACE FUNCTION lot_quantity_stays_with_its_ledger() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.quantity IS DISTINCT FROM OLD.quantity
     AND EXISTS (SELECT 1 FROM stock_ledger_entries WHERE lot_id = OLD.id) THEN
    RAISE EXCEPTION '로트 %의 수량은 원장에 줄이 선 뒤에 고치지 않는다 — 입고 줄과 갈린다',
      OLD.lot_number
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_LOT_QUANTITY_TRIGGER = """
CREATE TRIGGER lot_quantity_stays_with_its_ledger
BEFORE UPDATE OF quantity ON lots
FOR EACH ROW EXECUTE FUNCTION lot_quantity_stays_with_its_ledger()
"""

_EFFECT_FUNCTION = """
CREATE OR REPLACE FUNCTION txn_type_effect_stays_behind_its_lines() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.total_effect IS DISTINCT FROM OLD.total_effect
     AND EXISTS (SELECT 1 FROM stock_ledger_entries
                 WHERE txn_type_group = OLD.group_code AND txn_type = OLD.code) THEN
    RAISE EXCEPTION
      '유형 %의 총량 영향은 원장에 줄이 선 뒤에 고치지 않는다 — 잔량이 다시 세어진다',
      OLD.code
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_EFFECT_TRIGGER = """
CREATE TRIGGER txn_type_effect_stays_behind_its_lines
BEFORE UPDATE OF total_effect ON txn_type_attributes
FOR EACH ROW EXECUTE FUNCTION txn_type_effect_stays_behind_its_lines()
"""

_RETURN_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION purchase_return_stays_within_what_came() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  received double precision;
  judged_result text;
  judged timestamp;
  came_in timestamp;
  returned numeric;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION '반품 문서는 고치거나 지우지 않는다 — 일어난 일이다 (반품 %)', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  IF NOT (NEW.quantity > '-Infinity' AND NEW.quantity < 'Infinity') THEN
    RETURN NEW;
  END IF;

  SELECT quantity, result, judged_at INTO received, judged_result, judged
  FROM inspections WHERE id = NEW.inspection_id FOR NO KEY UPDATE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  IF NEW.returned_at < judged THEN
    RAISE EXCEPTION
      '반품 시각(%)이 판정 시각(%)보다 앞선다 — 판정 전의 물건은 돌려보낼 수 없다',
      NEW.returned_at, judged
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.lot_id IS NOT NULL THEN
    SELECT occurred_at INTO came_in FROM stock_ledger_entries
    WHERE lot_id = NEW.lot_id AND txn_type = '구매입고';
    IF NEW.returned_at < came_in THEN
      RAISE EXCEPTION
        '반품 시각(%)이 그 로트의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
        NEW.returned_at, came_in
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END IF;

  IF judged_result <> '불합격' THEN
    RETURN NEW;
  END IF;

  SELECT coalesce(sum(quantity::numeric), 0) INTO returned
  FROM purchase_returns
  WHERE inspection_id = NEW.inspection_id AND lot_id IS NULL;

  IF returned + NEW.quantity::numeric > received::numeric THEN
    RAISE EXCEPTION '검사 %에서 받은 것은 %인데 돌려보낸 합이 %이 된다',
      NEW.inspection_id, received, returned + NEW.quantity::numeric
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_RETURN_GUARD_TRIGGER = """
CREATE TRIGGER purchase_return_stays_within_what_came
BEFORE INSERT OR UPDATE OR DELETE ON purchase_returns
FOR EACH ROW EXECUTE FUNCTION purchase_return_stays_within_what_came()
"""

_RETURN_LINE_FUNCTION = """
CREATE OR REPLACE FUNCTION purchase_return_has_its_ledger_line() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.lot_id IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM stock_ledger_entries WHERE purchase_return_id = NEW.id) THEN
    RAISE EXCEPTION
      '반품 %는 재고 로트를 돌려보냈는데 원장에 줄이 없다 — 문서와 줄은 함께 선다',
      NEW.id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$
"""

_RETURN_LINE_TRIGGER = """
CREATE CONSTRAINT TRIGGER purchase_return_has_its_ledger_line
AFTER INSERT ON purchase_returns
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION purchase_return_has_its_ledger_line()
"""

_INSPECTION_FUNCTION = """
CREATE OR REPLACE FUNCTION inspection_stays_behind_its_returns() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.quantity, NEW.supplier_id, NEW.item_id, NEW.judged_at, NEW.received_date,
      NEW.nonconformity_code)
       IS DISTINCT FROM
     (OLD.quantity, OLD.supplier_id, OLD.item_id, OLD.judged_at, OLD.received_date,
      OLD.nonconformity_code)
     AND EXISTS (SELECT 1 FROM purchase_returns WHERE inspection_id = OLD.id) THEN
    RAISE EXCEPTION
      '검사 %를 반품이 가리킨다 — 수량 · 공급사 · 품목 · 시각 · 도착일 · 사유를 고치지 않는다',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_INSPECTION_TRIGGER = """
CREATE TRIGGER inspection_stays_behind_its_returns
BEFORE UPDATE OF quantity, supplier_id, item_id, judged_at, received_date, nonconformity_code
ON inspections
FOR EACH ROW EXECUTE FUNCTION inspection_stays_behind_its_returns()
"""

# ── 기준정보 — 「구매반품출고」의 설명 ──────────────────────────────────────
#
# 시드가 「대물정산」만 적어 두었는데 대금정산 반품도 같은 유형으로 원장에 난다 — 정산
# 구분은 반품 문서에 한 번만 산다. **시드가 심은 글자일 때만** 고친다: 사람이 이미 고쳐
# 둔 설명을 덮지 않고, 내릴 때도 이 리비전이 쓴 글자일 때만 되돌린다.
_RETURN_DESCRIPTION_BEFORE = "대물정산"
_RETURN_DESCRIPTION_AFTER = "대물 · 대금 모두 — 정산 구분은 반품 문서가 든다"


def upgrade() -> None:
    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inspection_id", sa.Integer(), nullable=False),
        sa.Column("inspection_result", sa.String(length=10), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=True),
        sa.Column("settle_type", sa.String(length=10), nullable=False),
        sa.Column(
            "settle_type_group",
            sa.String(length=20),
            server_default="SETTLE_TYPE",
            nullable=False,
        ),
        sa.Column("nonconformity_code", sa.String(length=30), nullable=True),
        sa.Column(
            "nonconformity_group",
            sa.String(length=20),
            server_default="NC_REASON",
            nullable=False,
        ),
        sa.Column("reason_stage", sa.String(length=30), server_default="IQC", nullable=False),
        sa.Column(
            "reason_stage_group",
            sa.String(length=20),
            server_default="INSP_STAGE",
            nullable=False,
        ),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("returned_at", sa.DateTime(), nullable=False),
        sa.Column("returned_by", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "(lot_id IS NULL) = (inspection_result = '불합격')",
            name="ck_purchase_return_lot_unless_failed",
        ),
        sa.CheckConstraint(
            "settle_type_group = 'SETTLE_TYPE'", name="ck_purchase_return_settle_type_group"
        ),
        sa.CheckConstraint(
            "nonconformity_group = 'NC_REASON'", name="ck_purchase_return_reason_group"
        ),
        sa.CheckConstraint(
            "(lot_id IS NULL) = (nonconformity_code IS NULL)",
            name="ck_purchase_return_reason_only_for_a_lot",
        ),
        sa.CheckConstraint(
            "reason_stage_group = 'INSP_STAGE' AND reason_stage = 'IQC'",
            name="ck_purchase_return_reason_stage",
        ),
        sa.CheckConstraint(
            "quantity > 0 AND quantity > '-Infinity'::double precision AND quantity < 'Infinity'::double precision",
            name="ck_purchase_return_quantity",
        ),
        sa.CheckConstraint(
            "btrim(returned_by, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_purchase_return_returned_by_is_present",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id", "inspection_result"],
            ["inspections.id", "inspections.result"],
            name="fk_purchase_return_inspection",
        ),
        sa.ForeignKeyConstraint(
            ["lot_id", "inspection_id"],
            ["lots.id", "lots.inspection_id"],
            name="fk_purchase_return_lot",
        ),
        sa.ForeignKeyConstraint(
            ["settle_type_group", "settle_type"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_purchase_return_settle_type",
        ),
        sa.ForeignKeyConstraint(
            ["nonconformity_group", "nonconformity_code", "reason_stage_group", "reason_stage"],
            [
                "nonconformity_stage_rules.reason_group",
                "nonconformity_stage_rules.reason_code",
                "nonconformity_stage_rules.stage_group",
                "nonconformity_stage_rules.stage_code",
            ],
            name="fk_purchase_return_reason",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "lot_id", "quantity", "returned_at", name="uq_purchase_return_ledger_match"
        ),
    )

    # ── 원장 — 반품 줄을 받는다 ────────────────────────────────────────────
    op.add_column(
        "stock_ledger_entries",
        sa.Column("purchase_return_id", sa.Integer(), nullable=True),
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_is_a_purchase_receipt", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source",
        "stock_ledger_entries",
        "txn_type IN ('구매입고', '구매반품출고')",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_return_names_its_document",
        "stock_ledger_entries",
        "(txn_type = '구매반품출고') = (purchase_return_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_purchase_return",
        "stock_ledger_entries",
        "purchase_returns",
        ["purchase_return_id", "lot_id", "quantity", "occurred_at"],
        ["id", "lot_id", "quantity", "returned_at"],
    )
    op.create_index("ix_stock_ledger_entry_lot", "stock_ledger_entries", ["lot_id"])
    op.create_index(
        "uq_stock_ledger_entry_one_line_per_return",
        "stock_ledger_entries",
        ["purchase_return_id"],
        unique=True,
        postgresql_where=sa.text("purchase_return_id IS NOT NULL"),
    )

    # ── 조이기 전에 묻는다 — 입고 줄과 로트 수량이 갈린 로트 ──────────────
    op.execute(
        """
        DO $$
        DECLARE adrift text;
        BEGIN
          SELECT string_agg(l.lot_number || ' (로트 ' || l.quantity || ' · 입고 ' || e.quantity || ')',
                            ', ' ORDER BY l.lot_number) INTO adrift
          FROM stock_ledger_entries AS e JOIN lots AS l ON l.id = e.lot_id
          WHERE e.txn_type = '구매입고' AND e.quantity IS DISTINCT FROM l.quantity;
          IF adrift IS NOT NULL THEN
            RAISE EXCEPTION
              '입고 줄의 수량이 로트 수량과 다르다: %. 어느 쪽이 실물인지 사람이 먼저 가른다',
              adrift;
          END IF;
        END $$;
        """
    )

    # ── 조이기 전에 묻는다 — 검사 수량과 로트 수량이 갈린 로트(감사 ㉟ NC-225) ──
    # 검사 한 건은 로트 하나를 통째로 만든다. 앞 스키마는 둘을 묶지 않았으므로 갈린 짝이
    # 실재할 수 있고, 외래키가 먼저 걸리면 나오는 말은 제약 이름뿐이다.
    op.execute(
        """
        DO $$
        DECLARE adrift text;
        BEGIN
          SELECT string_agg(l.lot_number || ' (로트 ' || l.quantity || ' · 검사 ' || i.quantity || ')',
                            ', ' ORDER BY l.lot_number) INTO adrift
          FROM lots AS l JOIN inspections AS i ON i.id = l.inspection_id
          WHERE l.quantity IS DISTINCT FROM i.quantity;
          IF adrift IS NOT NULL THEN
            RAISE EXCEPTION
              '로트 수량이 그 로트를 만든 검사 수량과 다르다: %. 어느 쪽이 들어온 양인지 사람이 먼저 가른다',
              adrift;
          END IF;
        END $$;
        """
    )
    op.create_unique_constraint("uq_inspection_id_quantity", "inspections", ["id", "quantity"])
    op.create_foreign_key(
        "fk_lot_inspection_quantity",
        "lots",
        "inspections",
        ["inspection_id", "quantity"],
        ["id", "quantity"],
    )

    for statement in (
        _LEDGER_GUARD_FUNCTION,
        _LEDGER_GUARD_TRIGGER,
        _LOT_QUANTITY_FUNCTION,
        _LOT_QUANTITY_TRIGGER,
        _EFFECT_FUNCTION,
        _EFFECT_TRIGGER,
        _RETURN_GUARD_FUNCTION,
        _RETURN_GUARD_TRIGGER,
        _RETURN_LINE_FUNCTION,
        _RETURN_LINE_TRIGGER,
        _INSPECTION_FUNCTION,
        _INSPECTION_TRIGGER,
    ):
        op.execute(statement)

    op.execute(
        sa.text(
            "UPDATE common_codes SET description = :after"
            " WHERE group_code = 'TXN_TYPE' AND code = '구매반품출고' AND description = :before"
        ).bindparams(after=_RETURN_DESCRIPTION_AFTER, before=_RETURN_DESCRIPTION_BEFORE)
    )


def downgrade() -> None:
    # **사라지는 것을 먼저 세고 멈춘다.** 반품은 공급사에게 간 물건의 기록이고 다시
    # 만들 수 없다. 누가 냈는지가 아니라 몇 건인지를 말한다 — 이 메시지는 서버 로그에도
    # 남는다(감사 ⑲ NC-173).
    op.execute(
        """
        DO $$
        DECLARE returned bigint;
        BEGIN
          SELECT count(*) INTO returned FROM purchase_returns;
          IF returned > 0 THEN
            RAISE EXCEPTION
              '되돌리면 반품 %건과 그 원장 줄이 사라진다. 공급사에게 간 물건이 장부에서 돌아온다',
              returned;
          END IF;
        END $$;
        """
    )

    op.execute(
        sa.text(
            "UPDATE common_codes SET description = :before"
            " WHERE group_code = 'TXN_TYPE' AND code = '구매반품출고' AND description = :after"
        ).bindparams(after=_RETURN_DESCRIPTION_AFTER, before=_RETURN_DESCRIPTION_BEFORE)
    )

    op.execute("DROP TRIGGER inspection_stays_behind_its_returns ON inspections")
    op.execute("DROP TRIGGER purchase_return_has_its_ledger_line ON purchase_returns")
    op.execute("DROP TRIGGER purchase_return_stays_within_what_came ON purchase_returns")
    op.execute("DROP TRIGGER txn_type_effect_stays_behind_its_lines ON txn_type_attributes")
    op.execute("DROP TRIGGER lot_quantity_stays_with_its_ledger ON lots")
    op.execute("DROP TRIGGER stock_ledger_entry_keeps_the_balance ON stock_ledger_entries")
    op.execute("DROP FUNCTION inspection_stays_behind_its_returns()")
    op.execute("DROP FUNCTION purchase_return_has_its_ledger_line()")
    op.execute("DROP FUNCTION purchase_return_stays_within_what_came()")
    op.execute("DROP FUNCTION txn_type_effect_stays_behind_its_lines()")
    op.execute("DROP FUNCTION lot_quantity_stays_with_its_ledger()")
    op.execute("DROP FUNCTION stock_ledger_entry_keeps_the_balance()")

    op.drop_constraint("fk_lot_inspection_quantity", "lots", type_="foreignkey")
    op.drop_constraint("uq_inspection_id_quantity", "inspections", type_="unique")

    op.drop_index(
        "uq_stock_ledger_entry_one_line_per_return", table_name="stock_ledger_entries"
    )
    op.drop_index("ix_stock_ledger_entry_lot", table_name="stock_ledger_entries")
    op.drop_constraint(
        "fk_stock_ledger_entry_purchase_return", "stock_ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_return_names_its_document", "stock_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_is_a_purchase_receipt",
        "stock_ledger_entries",
        "txn_type = '구매입고'",
    )
    op.drop_column("stock_ledger_entries", "purchase_return_id")
    op.drop_table("purchase_returns")
