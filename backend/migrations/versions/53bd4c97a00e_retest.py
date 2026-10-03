"""만료된 로트가 재검사로 돌아온다 — 재검사 · 폐기 줄 · 재검사를 지키는 트리거

검사 표가 `재검사` 단계를 받고, 원장이 폐기출고를 받는다. 재검사는 로트를 만들지 않고
있는 로트를 가리키며(`target_lot_id`), 합격하면 갱신 만료일이 그 줄에 박히고(ADR 0017)
불합격하면 그 로트의 잔량 전부가 폐기출고 한 줄로 나간다. 「만료된 로트만」은 다른 표의
여러 줄을 보는 조건이라 트리거가 건다(ADR 0016). 3단계 재검사 조각의 스키마다.

**IQC 에만 뜻이 있는 칸이 빌 수 있게 된다** — 공급사 · 공급사 로트번호 · 입고 수량. 재검사는
들어온 물건이 아니다. 단계마다 무엇이 차는지는 CHECK 가 조인다.

**측정 줄이 검사의 단계를 든다.** 재검사 측정은 경시변화 기준만 가리키게 쌍 외래키를 거는데,
그러려면 측정 줄이 「재검사인가」를 알아야 한다. 이 리비전 전의 측정 줄은 전부 IQC 의 것이라
그 검사에서 단계를 옮겨 채운다.

**트리거 SQL 은 모델 쪽과 같은 글자다** — `app/db/ledger_guards.py`. 원장의 잔량 트리거는
폐기 줄이 잔량 전부인지를 보도록 본문이 바뀌므로 `CREATE OR REPLACE` 로 갈아 끼우고, 내릴
때 앞 리비전의 글자로 되돌린다.

**올릴 때 묻는 것이 없다.** 새 제약이 옛 줄에 걸리는 자리를 찾아봤다 — 옛 검사는 전부 IQC 라
단계마다 차는 칸을 이미 채우고, 반품은 IQC 를 가리키며, 원장에는 폐기 줄이 없다. 로트의 만료일을
고정하는 트리거는 지금 있는 값을 묻지 않는다 — 그 값이 라벨에 찍혀 나간 값이다.

**올릴 때 잠근다.** 칸이나 유일키를 더하는 표(`inspections` · `inspection_measurements` ·
`stock_ledger_entries` · `lots` · `process_inspection_standards`)와 트리거가 걸리는 표에 ACCESS
EXCLUSIVE 가 커밋까지 남는다(목록을 세지 않는다) — 읽기까지 멈춘다. `purchase_returns` 는 외래키
하나만 받아 SHARE ROW EXCLUSIVE 다 — 쓰기만 멈춘다(감사 ㊳). 잠금의 길이는 행 수가 정한다 — CHECK ·
외래키 · `SET NOT NULL` 이 옛 줄 전부를 검증하고, 유일키와 인덱스가 만들어지며, 측정 줄 전부에 단계를
옮겨 채우는 `UPDATE` 가 그 잠금 아래에서 돈다. 행 수에 비례하는 그 구간이다. `migrations/env.py` 가
전체를 트랜잭션 하나로 감싼다.

**내릴 때 멈춘다 — 재검사가 하나라도 있으면.** 이 리비전은 구조만 세우므로 사라지는 것은 사람이
나중에 넣은 재검사뿐이고, 그것은 다시 만들 수 없다 — 그 판정과 갱신 만료일, 폐기 줄의 근거가
이 표에만 있다. 폐기 줄은 재검사 없이 설 수 없으므로(외래키) 재검사를 세면 둘 다 센다(W-6 ①).
**세기 전에 잠근다** — 재검사를 넣는 트랜잭션이 커밋되기 전에 세면 0 을 보고 지나간다.

**내릴 때도 잠근다**(감사 ㊳). `DROP TRIGGER` 가 `lots` · `inspections` 에 ACCESS EXCLUSIVE 를 잡아
두 표의 **읽기까지** 커밋까지 멈춘다. 원장과 검사의 CHECK 를 앞 리비전의 모양으로 다시 세우고 칸을
`SET NOT NULL` 로 되돌리며 모든 줄을 다시 검증한다 — 올릴 때와 같이 행 수에 비례하는 구간이다.

> **이 가드가 못 보는 부류**(W-6 ③): 재검사 없이 원장에 직접 넣은 폐기 줄 — 이 리비전의
> 외래키가 서는 동안 설 수 없다.

Revision ID: 53bd4c97a00e
Revises: 85d4ad8b3f1f
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "53bd4c97a00e"
down_revision: str | None = "85d4ad8b3f1f"
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

_RETEST_ADMISSION_FUNCTION = """
CREATE OR REPLACE FUNCTION retest_comes_only_to_an_expired_lot() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_label text;
  labelled date;
  expires date;
  latest timestamp;
  balance numeric;
BEGIN
  IF NEW.inspection_stage <> '재검사' OR NEW.target_lot_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT lot_number, expiry_date INTO lot_label, labelled
  FROM lots WHERE id = NEW.target_lot_id FOR NO KEY UPDATE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  IF EXISTS (SELECT 1 FROM inspections
             WHERE target_lot_id = NEW.target_lot_id
               AND result = '불합격') THEN
    RAISE EXCEPTION '로트 %는 이미 재검사에서 떨어졌다 — 폐기된 로트는 다시 검사하지 않는다',
      lot_label
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT max(judged_at) INTO latest FROM inspections WHERE target_lot_id = NEW.target_lot_id;
  IF NEW.judged_at < latest THEN
    RAISE EXCEPTION '재검사의 판정 시각(%)이 로트 %의 앞선 재검사(%)보다 이르다',
      NEW.judged_at, lot_label, latest
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT renewed_expiry_date INTO expires FROM inspections
  WHERE target_lot_id = NEW.target_lot_id AND result = '합격'
  ORDER BY judged_at DESC, id DESC LIMIT 1;
  IF NOT FOUND THEN
    expires := labelled;
  END IF;

  IF expires IS NULL THEN
    RAISE EXCEPTION '로트 %는 만료일이 없다 — 재검사는 만료된 로트의 일이다', lot_label
      USING ERRCODE = 'check_violation';
  END IF;
  IF expires >= NEW.judged_at::date THEN
    RAISE EXCEPTION '로트 %의 지금 만료일(%)이 판정일(%)보다 앞서지 않는다 — %',
      lot_label, expires, NEW.judged_at::date, '만료되지 않은 로트는 재검사를 받지 않는다'
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT coalesce(sum(CASE a.total_effect
                        WHEN '증가' THEN e.quantity::numeric
                        WHEN '감소' THEN -e.quantity::numeric
                      END), 0)
    INTO balance
  FROM stock_ledger_entries AS e
  JOIN txn_type_attributes AS a ON a.group_code = e.txn_type_group AND a.code = e.txn_type
  WHERE e.lot_id = NEW.target_lot_id;

  IF balance <= 0 THEN
    RAISE EXCEPTION '로트 %에 남은 것이 없다 — 없는 물건은 재검사하지 않는다', lot_label
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_RETEST_ADMISSION_TRIGGER = """
CREATE TRIGGER retest_comes_only_to_an_expired_lot
BEFORE INSERT ON inspections
FOR EACH ROW EXECUTE FUNCTION retest_comes_only_to_an_expired_lot()
"""

_INSPECTION_STAGE_FUNCTION = """
CREATE OR REPLACE FUNCTION inspection_keeps_its_stage() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.inspection_stage = '재검사' THEN
      RAISE EXCEPTION '재검사 %는 지우지 않는다 — 그 로트의 지금 만료일이 그 위에 서 있다',
        OLD.id
        USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
  END IF;

  IF NEW.inspection_stage IS DISTINCT FROM OLD.inspection_stage THEN
    RAISE EXCEPTION '검사 %의 단계는 바뀌지 않는다 — 줄은 들어올 때의 단계로 산다', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  IF OLD.inspection_stage = '재검사' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION '재검사 %는 고치지 않는다 — 그 로트의 지금 만료일이 그 위에 서 있다',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_INSPECTION_STAGE_TRIGGER = """
CREATE TRIGGER inspection_keeps_its_stage
BEFORE UPDATE OR DELETE ON inspections
FOR EACH ROW EXECUTE FUNCTION inspection_keeps_its_stage()
"""

_LOT_EXPIRY_FUNCTION = """
CREATE OR REPLACE FUNCTION lot_expiry_stays_as_labelled() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.expiry_date IS DISTINCT FROM OLD.expiry_date THEN
    RAISE EXCEPTION '로트 %의 만료일은 고치지 않는다 — 갱신된 만료일은 재검사 기록에 산다',
      OLD.lot_number
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

_LOT_EXPIRY_TRIGGER = """
CREATE TRIGGER lot_expiry_stays_as_labelled
BEFORE UPDATE OF expiry_date ON lots
FOR EACH ROW EXECUTE FUNCTION lot_expiry_stays_as_labelled()
"""

_RETEST_LINE_FUNCTION = """
CREATE OR REPLACE FUNCTION retest_failure_has_its_disposal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.inspection_stage = '재검사'
     AND NEW.result = '불합격'
     AND NOT EXISTS (SELECT 1 FROM stock_ledger_entries WHERE retest_id = NEW.id) THEN
    RAISE EXCEPTION
      '재검사 %는 로트를 떨어뜨렸는데 원장에 폐기 줄이 없다 — 판정과 폐기는 함께 선다',
      NEW.id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$
"""

_RETEST_LINE_TRIGGER = """
CREATE CONSTRAINT TRIGGER retest_failure_has_its_disposal_line
AFTER INSERT ON inspections
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION retest_failure_has_its_disposal_line()
"""


# **앞 리비전(`85d4ad8b3f1f`)의 잔량 트리거** — 내릴 때 이 글자로 되돌린다.
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
  expected := CASE NEW.txn_type WHEN '구매입고' THEN '증가' WHEN '구매반품출고' THEN '감소' END;
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

  RETURN NEW;
END $$
"""

# ── 기준정보 — 「폐기출고」의 근거 문서 ────────────────────────────────────
#
# 시드가 「재작업 불가 · OQC 불합격」만 적어 두었는데 재검사 불합격도 같은 유형으로 원장에 난다.
# **시드가 심은 글자일 때만** 고치고, 내릴 때도 이 리비전이 쓴 글자일 때만 되돌린다.
_DISPOSAL_SOURCE_BEFORE = "재작업 불가 · OQC 불합격"
_DISPOSAL_SOURCE_AFTER = "재작업 불가 · OQC 불합격 · 재검사 불합격"


def upgrade() -> None:
    # ── 검사 — 재검사를 받는다 ─────────────────────────────────────────────
    op.alter_column("inspections", "supplier_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "inspections", "supplier_lot_number", existing_type=sa.String(length=50), nullable=True
    )
    op.alter_column("inspections", "quantity", existing_type=sa.Float(), nullable=True)
    op.add_column("inspections", sa.Column("target_lot_id", sa.Integer(), nullable=True))
    op.add_column("inspections", sa.Column("renewed_expiry_date", sa.Date(), nullable=True))

    op.drop_constraint("ck_inspection_stage_is_incoming", "inspections", type_="check")
    op.create_check_constraint(
        "ck_inspection_stage_is_built", "inspections", "inspection_stage IN ('IQC', '재검사')"
    )
    op.create_check_constraint(
        "ck_inspection_delivery_only_for_incoming",
        "inspections",
        "inspection_stage = 'IQC' OR (supplier_id IS NULL AND supplier_lot_number IS NULL AND quantity IS NULL AND received_date IS NULL)",
    )
    op.create_check_constraint(
        "ck_inspection_incoming_names_its_delivery",
        "inspections",
        "inspection_stage <> 'IQC' OR (supplier_id IS NOT NULL AND supplier_lot_number IS NOT NULL AND quantity IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inspection_target_lot_only_for_retest",
        "inspections",
        "(inspection_stage = '재검사') = (target_lot_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inspection_renewal_only_for_a_passed_retest",
        "inspections",
        "(inspection_stage = '재검사' AND result = '합격') = (renewed_expiry_date IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inspection_renewal_after_judgement",
        "inspections",
        "renewed_expiry_date IS NULL OR renewed_expiry_date >= judged_at::date",
    )
    op.create_check_constraint(
        "ck_inspection_retest_has_no_special_acceptance",
        "inspections",
        "inspection_stage <> '재검사' OR result <> '특채'",
    )
    op.create_unique_constraint(
        "uq_inspection_id_stage", "inspections", ["id", "inspection_stage"]
    )
    op.create_unique_constraint(
        "uq_inspection_retest_ledger_match",
        "inspections",
        ["id", "target_lot_id", "result", "judged_at"],
    )
    op.create_index("ix_inspection_target_lot", "inspections", ["target_lot_id"])

    op.create_unique_constraint("uq_lot_id_item", "lots", ["id", "item_id"])
    op.create_foreign_key(
        "fk_inspection_target_lot",
        "inspections",
        "lots",
        ["target_lot_id", "item_id"],
        ["id", "item_id"],
    )

    # ── 측정 — 재검사는 경시변화 기준만 ────────────────────────────────────
    op.create_unique_constraint(
        "uq_inspection_standard_time_variant",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group", "time_variant"],
        postgresql_nulls_not_distinct=True,
    )
    op.add_column(
        "inspection_measurements",
        sa.Column("inspection_stage", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "inspection_measurements",
        sa.Column("standard_time_variant", sa.Boolean(), nullable=True),
    )
    # **옮겨 채운다** — 지어내지 않는다. 이 리비전 전의 측정 줄은 IQC 의 것뿐이지만, 그것을
    # 상수로 박지 않고 그 검사가 든 단계를 가져온다.
    op.execute(
        "UPDATE inspection_measurements AS m SET inspection_stage = i.inspection_stage"
        " FROM inspections AS i WHERE i.id = m.inspection_id"
    )
    op.alter_column(
        "inspection_measurements",
        "inspection_stage",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_inspection_measurement_stage",
        "inspection_measurements",
        "inspections",
        ["inspection_id", "inspection_stage"],
        ["id", "inspection_stage"],
    )
    op.create_foreign_key(
        "fk_inspection_measurement_time_variant",
        "inspection_measurements",
        "process_inspection_standards",
        ["process_code", "item_code", "material_group", "standard_time_variant"],
        ["process_code", "item_code", "material_group", "time_variant"],
    )
    op.create_check_constraint(
        "ck_inspection_measurement_time_variant_only_for_retest",
        "inspection_measurements",
        "(inspection_stage = '재검사') = (standard_time_variant IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_inspection_measurement_retest_is_time_variant",
        "inspection_measurements",
        "standard_time_variant IS NOT FALSE",
    )

    # ── 반품 — IQC 만 가리킨다 ─────────────────────────────────────────────
    op.create_foreign_key(
        "fk_purchase_return_inspection_stage",
        "purchase_returns",
        "inspections",
        ["inspection_id", "reason_stage"],
        ["id", "inspection_stage"],
    )

    # ── 원장 — 폐기 줄을 받는다 ────────────────────────────────────────────
    op.add_column("stock_ledger_entries", sa.Column("retest_id", sa.Integer(), nullable=True))
    op.add_column(
        "stock_ledger_entries",
        sa.Column("retest_result", sa.String(length=10), nullable=True),
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source",
        "stock_ledger_entries",
        "txn_type IN ('구매입고', '구매반품출고', '폐기출고')",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_disposal_names_its_retest",
        "stock_ledger_entries",
        "(txn_type = '폐기출고') = (retest_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_disposal_follows_a_failure",
        "stock_ledger_entries",
        "(retest_id IS NULL) = (retest_result IS NULL) AND (retest_result IS NULL OR retest_result = '불합격')",
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_retest",
        "stock_ledger_entries",
        "inspections",
        ["retest_id", "lot_id", "retest_result", "occurred_at"],
        ["id", "target_lot_id", "result", "judged_at"],
    )
    op.create_index(
        "uq_stock_ledger_entry_one_line_per_retest",
        "stock_ledger_entries",
        ["retest_id"],
        unique=True,
        postgresql_where=sa.text("retest_id IS NOT NULL"),
    )

    for statement in (
        _LEDGER_GUARD_FUNCTION,
        _RETEST_ADMISSION_FUNCTION,
        _RETEST_ADMISSION_TRIGGER,
        _INSPECTION_STAGE_FUNCTION,
        _INSPECTION_STAGE_TRIGGER,
        _LOT_EXPIRY_FUNCTION,
        _LOT_EXPIRY_TRIGGER,
        _RETEST_LINE_FUNCTION,
        _RETEST_LINE_TRIGGER,
    ):
        op.execute(statement)

    op.execute(
        sa.text(
            "UPDATE txn_type_attributes SET source_document_type = :after"
            " WHERE group_code = 'TXN_TYPE' AND code = '폐기출고'"
            " AND source_document_type = :before"
        ).bindparams(after=_DISPOSAL_SOURCE_AFTER, before=_DISPOSAL_SOURCE_BEFORE)
    )


def downgrade() -> None:
    # **세기 전에 잠근다.** 재검사를 넣는 트랜잭션이 커밋되기 전에 세면 0 을 보고 지나가고, 뒤의
    # 칸 지우기가 그 트랜잭션을 기다렸다가 커밋된 재검사째 지운다. `SHARE` 는 넣기와 부딪쳐 쓰는
    # 쪽이 끝난 뒤에 세게 하고, 그 뒤의 쓰기는 이 트랜잭션이 끝날 때까지 막는다.
    op.execute("LOCK TABLE inspections IN SHARE MODE")
    # **사라지는 것을 먼저 세고 멈춘다.** 몇 건인지를 말한다 — 메시지는 서버 로그에도 남는다.
    op.execute(
        """
        DO $$
        DECLARE retested bigint;
        BEGIN
          SELECT count(*) INTO retested FROM inspections WHERE inspection_stage = '재검사';
          IF retested > 0 THEN
            RAISE EXCEPTION
              '되돌리면 재검사 %건과 그 폐기 줄이 사라진다. 갱신된 만료일과 폐기의 근거가 함께 간다',
              retested;
          END IF;
        END $$;
        """
    )

    op.execute(
        sa.text(
            "UPDATE txn_type_attributes SET source_document_type = :before"
            " WHERE group_code = 'TXN_TYPE' AND code = '폐기출고'"
            " AND source_document_type = :after"
        ).bindparams(after=_DISPOSAL_SOURCE_AFTER, before=_DISPOSAL_SOURCE_BEFORE)
    )

    op.execute("DROP TRIGGER retest_failure_has_its_disposal_line ON inspections")
    op.execute("DROP TRIGGER lot_expiry_stays_as_labelled ON lots")
    op.execute("DROP TRIGGER inspection_keeps_its_stage ON inspections")
    op.execute("DROP TRIGGER retest_comes_only_to_an_expired_lot ON inspections")
    op.execute("DROP FUNCTION retest_failure_has_its_disposal_line()")
    op.execute("DROP FUNCTION lot_expiry_stays_as_labelled()")
    op.execute("DROP FUNCTION inspection_keeps_its_stage()")
    op.execute("DROP FUNCTION retest_comes_only_to_an_expired_lot()")
    op.execute(_LEDGER_GUARD_FUNCTION_BEFORE)

    op.drop_index(
        "uq_stock_ledger_entry_one_line_per_retest", table_name="stock_ledger_entries"
    )
    op.drop_constraint(
        "fk_stock_ledger_entry_retest", "stock_ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_disposal_follows_a_failure",
        "stock_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_disposal_names_its_retest", "stock_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source",
        "stock_ledger_entries",
        "txn_type IN ('구매입고', '구매반품출고')",
    )
    op.drop_column("stock_ledger_entries", "retest_result")
    op.drop_column("stock_ledger_entries", "retest_id")

    op.drop_constraint(
        "fk_purchase_return_inspection_stage", "purchase_returns", type_="foreignkey"
    )

    op.drop_constraint(
        "ck_inspection_measurement_retest_is_time_variant",
        "inspection_measurements",
        type_="check",
    )
    op.drop_constraint(
        "ck_inspection_measurement_time_variant_only_for_retest",
        "inspection_measurements",
        type_="check",
    )
    op.drop_constraint(
        "fk_inspection_measurement_time_variant", "inspection_measurements", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_inspection_measurement_stage", "inspection_measurements", type_="foreignkey"
    )
    op.drop_column("inspection_measurements", "standard_time_variant")
    op.drop_column("inspection_measurements", "inspection_stage")
    op.drop_constraint(
        "uq_inspection_standard_time_variant", "process_inspection_standards", type_="unique"
    )

    op.drop_constraint("fk_inspection_target_lot", "inspections", type_="foreignkey")
    op.drop_constraint("uq_lot_id_item", "lots", type_="unique")

    op.drop_index("ix_inspection_target_lot", table_name="inspections")
    op.drop_constraint("uq_inspection_retest_ledger_match", "inspections", type_="unique")
    op.drop_constraint("uq_inspection_id_stage", "inspections", type_="unique")
    for name in (
        "ck_inspection_retest_has_no_special_acceptance",
        "ck_inspection_renewal_after_judgement",
        "ck_inspection_renewal_only_for_a_passed_retest",
        "ck_inspection_target_lot_only_for_retest",
        "ck_inspection_incoming_names_its_delivery",
        "ck_inspection_delivery_only_for_incoming",
        "ck_inspection_stage_is_built",
    ):
        op.drop_constraint(name, "inspections", type_="check")
    op.create_check_constraint(
        "ck_inspection_stage_is_incoming", "inspections", "inspection_stage = 'IQC'"
    )
    op.drop_column("inspections", "renewed_expiry_date")
    op.drop_column("inspections", "target_lot_id")
    op.alter_column("inspections", "quantity", existing_type=sa.Float(), nullable=False)
    op.alter_column(
        "inspections", "supplier_lot_number", existing_type=sa.String(length=50), nullable=False
    )
    op.alter_column("inspections", "supplier_id", existing_type=sa.Integer(), nullable=False)
