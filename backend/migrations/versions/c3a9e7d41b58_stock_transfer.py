"""이동 — 요청 · 종결 · 이동 줄, 그리고 잔량을 로트 × 창고로 (4단계, ADR 0022 · 0023)

표 둘을 세운다 — 이동 요청(`stock_transfer_requests`)과 그 끝(`stock_transfer_closures`). 원장이
`생산출고` · `생산입고` 를 받고, 그 줄은 자기를 낸 처리 종결을 **같은 로트 · 같은 수량 · 같은 시각 ·
처리까지** 가리킨다. 처리 하나에 출고 줄 하나 · 입고 줄 하나다.

**잔량을 로트 × 창고로 센다.** 이동이 서면 로트 하나가 두 창고에 나뉘므로 원장 잔량 트리거
(`stock_ledger_entry_keeps_the_balance`)가 창고마다 합을 센다. 나뉜 로트가 재검사에서 떨어지면 잔량이
남은 창고마다 폐기 줄이 선다 — 폐기 줄의 유일 인덱스가 `(retest_id)` 에서 `(retest_id, warehouse)` 로
넓어지고, 0 짜리 폐기 줄을 받지 않으며, 재검사의 지연 트리거
(`retest_failure_has_its_disposal_line`)가 커밋 때 로트의 잔량이 0 인지까지 본다.

**새 트리거** — 요청은 로트가 들어온 뒤에만 서고(`stock_transfer_request_comes_after_the_receipt`),
만료된 로트의 처리를 받지 않고(`stock_transfer_closure_moves_only_a_live_lot`), 처리는 커밋 때 원장 두
줄을 가진다(`stock_transfer_processing_has_its_ledger_lines`). 요청과 종결은 고치지도 지우지도 않는다.
글자는 `app/db/ledger_guards.py` 와 같다 — 둘이 갈리면 `tests/test_migrations.py` 가 잡는다.

**올릴 때 묻는다 — 조이기 전에.** 잔량이 로트 하나로 세어지던 동안에는 폐기 줄이 로트가 한 번도
있지 않은 창고에도 설 수 있었다(폐기는 창고를 고르지 않는다 — 쓰기 경로는 내지 않는다). 그런 줄은
바뀐 트리거 아래에서 그 창고의 합을 음수로 만든다(감사 ㊸ OB-1). 그리고 0 짜리 폐기 줄은 새 CHECK 가
제약 이름만 내놓고 멈춘다. 둘 다 가드가 먼저 로트 번호를 말하고 멈춘다. 옛 원장이 받던 다른 줄은
새 제약에 걸리지 않는다 — 이동 줄이 없어 종결 칸이 비고, 입고 · 반품 줄은 이미 원재료창고에 섰다.
폐기 줄의 유일 인덱스를 넓히는 것은 받던 줄을 거절하지 않는다.

**올릴 때 잠근다.** 맨 앞에서 원장을 SHARE ROW EXCLUSIVE 로 잠근다 — 가드가 센 뒤 트리거가 바뀌기
전에 옛 버전의 트랜잭션이 옛 셈으로 줄을 넣지 못하게. 칸을 더하는 `ADD COLUMN` 에서 ACCESS EXCLUSIVE 로
올라가 커밋까지 원장의 **읽기까지** 멈춘다. 새 CHECK 와 외래키 · 유일 인덱스가 원장의 옛 줄 전부를
지나므로 잠금의 길이는 원장의 행 수가 정한다. 새 표의 외래키는 `lots` 를, 트리거는 그것이 걸리는 표를
잡는다. `migrations/env.py` 가 전체를 트랜잭션 하나로 감싼다.

**내릴 때 멈출 수 있다 — 이동 요청이 하나라도 있으면.** 이 리비전은 구조만 세우므로 사라지는 것은
사람이 나중에 낸 요청 · 종결과 처리가 낸 원장 줄이고, 그것은 **다시 만들 수 없다**(W-6 ①). 종결은
요청 없이, 이동 줄은 종결 없이 설 수 없으므로(외래키) 요청을 세면 셋 다 센다. 나뉜 로트의 폐기 줄도
이동이 있어야 서므로 같은 가드가 막는다. **세기 전에 잠근다** — 요청을 넣는 트랜잭션이 커밋되기 전에
세면 0 을 보고 지나간다.

**내릴 때도 잠근다.** 세는 동안 요청 표는 SHARE 다. 그 뒤 `DROP TRIGGER` 와 칸 · 제약 · 표를 지우는 것이
두 새 표와 원장에, 요청 표를 지우는 것이 그 외래키를 떼며 `lots` 에 ACCESS EXCLUSIVE 를 잡아 **읽기까지**
커밋까지 멈춘다. 함수를 되돌리는 `CREATE OR REPLACE FUNCTION` 은 표를 잠그지 않는다. 원장 쪽은 옛 CHECK 를
다시 세우며 모든 줄을 다시 검증한다.

> **이 가드들이 못 보는 부류**(W-6 ③): 올릴 때의 가드는 줄의 **합**을 본다 — 잔량이 로트 하나로 세어지던
> 동안 들어오는 줄이 입고 줄 하나뿐이었으므로 합이 음수가 아니면 어느 시점에도 음수가 아니었다. 내릴 때의
> 가드는 요청을 세므로, 요청 없이 원장에 직접 넣은 이동 줄은 볼 수 없는데 그런 줄은 이 리비전의 외래키가
> 서는 동안 설 수 없다.
>
> **잠금 순서는 옛 입고 경로와 반대다**(audit-data 관찰, 2026-10-20). 올릴 때 원장을 먼저, 새 표의 외래키가
> `lots` 를 나중에 잡는다. 옛 버전의 IQC 입고는 로트를 넣고 원장 줄을 넣으므로, 둘이 함께 돌면 교착이 나
> PostgreSQL 이 하나를 끊는다 — 시끄러운 실패이고 롤백된다. 배포처가 없어 옛 버전이 함께 돌지 않으므로
> 그대로 두었다(저장소 소유자, 2026-10-20). 배포처가 서는 단계에서 `lots` 를 먼저 잡는 순서로 다시 본다.

Revision ID: c3a9e7d41b58
Revises: 1e5667151a9f
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3a9e7d41b58"
down_revision: str | None = "1e5667151a9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── 트리거 — `app/db/ledger_guards.py` 와 같은 글자 ─────────────────────────

_LEDGER_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_ledger_entry_keeps_the_balance() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_quantity double precision;
  lot_warehouse text;
  lot_item_type text;
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

  SELECT quantity, warehouse, item_type, lot_number
    INTO lot_quantity, lot_warehouse, lot_item_type, lot_label
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

  IF NEW.item_type IS DISTINCT FROM lot_item_type
     OR NOT ((NEW.warehouse = '원재료' AND NEW.item_type IN ('원자재')) OR (NEW.warehouse = '생산' AND NEW.item_type IN ('원자재', '반제품', '완제품')) OR (NEW.warehouse = '제품' AND NEW.item_type IN ('완제품')))
     OR NOT ((NEW.txn_type <> '구매입고' OR NEW.warehouse = '원재료') AND (NEW.txn_type <> '구매반품출고' OR NEW.warehouse = '원재료') AND (NEW.txn_type <> '생산출고' OR NEW.warehouse = '원재료') AND (NEW.txn_type <> '생산입고' OR NEW.warehouse = '생산')) THEN
    RETURN NEW;
  END IF;

  SELECT total_effect INTO effect FROM txn_type_attributes
  WHERE group_code = NEW.txn_type_group AND code = NEW.txn_type FOR SHARE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;
  expected := CASE NEW.txn_type WHEN '구매입고' THEN '증가' WHEN '구매반품출고' THEN '감소' WHEN '폐기출고' THEN '감소' WHEN '생산출고' THEN '감소' WHEN '생산입고' THEN '증가' END;
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
  WHERE e.lot_id = NEW.lot_id AND e.warehouse = NEW.warehouse;

  IF effect = '증가' THEN
    balance := balance + NEW.quantity::numeric;
  ELSE
    balance := balance - NEW.quantity::numeric;
  END IF;

  IF balance < 0 THEN
    RAISE EXCEPTION '로트 %의 % 창고 잔량이 %이 된다 — 그 창고에 있는 것보다 많이 뺄 수 없다',
      lot_label, NEW.warehouse, balance
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type = '폐기출고' AND balance <> 0 THEN
    RAISE EXCEPTION '폐기출고는 로트 %의 % 창고 잔량 전부다 — %이 남는다',
      lot_label, NEW.warehouse, balance
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_RETEST_LINE_FUNCTION = """
CREATE OR REPLACE FUNCTION retest_failure_has_its_disposal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_label text;
  remaining numeric;
BEGIN
  IF NEW.inspection_stage IS DISTINCT FROM '재검사'
     OR NEW.result IS DISTINCT FROM '불합격' THEN
    RETURN NULL;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM stock_ledger_entries WHERE retest_id = NEW.id) THEN
    RAISE EXCEPTION
      '재검사 %는 로트를 떨어뜨렸는데 원장에 폐기 줄이 없다 — 판정과 폐기는 함께 선다',
      NEW.id
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT coalesce(sum(CASE a.total_effect
                        WHEN '증가' THEN e.quantity::numeric
                        WHEN '감소' THEN -e.quantity::numeric
                      END), 0)
    INTO remaining
  FROM stock_ledger_entries AS e
  JOIN txn_type_attributes AS a ON a.group_code = e.txn_type_group AND a.code = e.txn_type
  WHERE e.lot_id = NEW.target_lot_id;

  IF remaining <> 0 THEN
    SELECT lot_number INTO lot_label FROM lots WHERE id = NEW.target_lot_id;
    RAISE EXCEPTION
      '재검사 %는 로트 %를 떨어뜨렸는데 %이 남는다 — 잔량이 남은 창고마다 폐기 줄이 선다',
      NEW.id, lot_label, remaining
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$
"""

_TRANSFER_REQUEST_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_transfer_request_comes_after_the_receipt() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_label text;
  came_in timestamp;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION
      '이동 요청은 고치거나 지우지 않는다 — 잘못 낸 요청은 취소하고 새로 낸다 (요청 %)',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  SELECT lot_number INTO lot_label FROM lots WHERE id = NEW.lot_id;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  SELECT occurred_at INTO came_in FROM stock_ledger_entries
  WHERE lot_id = NEW.lot_id AND txn_type = '구매입고';
  IF NOT FOUND THEN
    RAISE EXCEPTION '로트 %에 입고 줄이 없다 — 들어왔다는 사실이 없는 로트는 옮기지 않는다',
      lot_label
      USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.requested_at < came_in THEN
    RAISE EXCEPTION
      '요청 시각(%)이 로트 %의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
      NEW.requested_at, lot_label, came_in
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_TRANSFER_REQUEST_TRIGGER = """
CREATE TRIGGER stock_transfer_request_comes_after_the_receipt
BEFORE INSERT OR UPDATE OR DELETE ON stock_transfer_requests
FOR EACH ROW EXECUTE FUNCTION stock_transfer_request_comes_after_the_receipt()
"""

_TRANSFER_CLOSURE_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_transfer_closure_moves_only_a_live_lot() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_label text;
  labelled date;
  expires date;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION '이동 종결은 고치거나 지우지 않는다 — 일어난 일이다 (종결 %)', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  IF NEW.closure_type IS DISTINCT FROM '처리' THEN
    RETURN NEW;
  END IF;

  SELECT lot_number, expiry_date INTO lot_label, labelled
  FROM lots WHERE id = NEW.lot_id;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  SELECT renewed_expiry_date INTO expires FROM inspections
  WHERE target_lot_id = NEW.lot_id AND result = '합격'
    AND judged_at <= NEW.closed_at
  ORDER BY judged_at DESC, id DESC LIMIT 1;
  IF NOT FOUND THEN
    expires := labelled;
  END IF;

  IF expires < NEW.closed_at::date THEN
    RAISE EXCEPTION '로트 %의 처리 시각 만료일(%)이 처리일(%)보다 앞선다 — %',
      lot_label, expires, NEW.closed_at::date, '만료된 로트는 옮기지 않는다'
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

_TRANSFER_CLOSURE_TRIGGER = """
CREATE TRIGGER stock_transfer_closure_moves_only_a_live_lot
BEFORE INSERT OR UPDATE OR DELETE ON stock_transfer_closures
FOR EACH ROW EXECUTE FUNCTION stock_transfer_closure_moves_only_a_live_lot()
"""

_TRANSFER_LINES_FUNCTION = """
CREATE OR REPLACE FUNCTION stock_transfer_processing_has_its_ledger_lines() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.closure_type = '처리'
     AND (NOT EXISTS (SELECT 1 FROM stock_ledger_entries
                      WHERE transfer_closure_id = NEW.id
                        AND txn_type = '생산출고')
          OR NOT EXISTS (SELECT 1 FROM stock_ledger_entries
                         WHERE transfer_closure_id = NEW.id
                           AND txn_type = '생산입고')) THEN
    RAISE EXCEPTION
      '처리 %에 원장의 %과 % 두 줄이 다 서지 않았다 — 처리와 두 줄은 함께 선다',
      NEW.id, '생산출고', '생산입고'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$
"""

_TRANSFER_LINES_TRIGGER = """
CREATE CONSTRAINT TRIGGER stock_transfer_processing_has_its_ledger_lines
AFTER INSERT ON stock_transfer_closures
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION stock_transfer_processing_has_its_ledger_lines()
"""

# 앞 리비전들의 글자 — 내릴 때 되돌린다. 잔량 트리거는 `1e5667151a9f`, 재검사의 지연 트리거는
# `53bd4c97a00e` 의 것이다.
_LEDGER_GUARD_FUNCTION_BEFORE = """
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

_RETEST_LINE_FUNCTION_BEFORE = """
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


def upgrade() -> None:
    # **묻기 전에 원장을 잠근다.** 가드가 센 뒤, 트리거가 바뀌기 전에 옛 버전의 트랜잭션이 옛 셈(로트
    # 하나의 합)으로 들어온 적 없는 창고의 폐기 줄을 넣으면 가드는 그 줄을 보지 못한다. `SHARE ROW
    # EXCLUSIVE` 는 쓰는 쪽(`ROW EXCLUSIVE`)이 끝나기를 기다렸다가 그 뒤의 쓰기를 커밋까지 막는다 —
    # 읽기는 막지 않는다. 뒤에 칸을 더하며 ACCESS EXCLUSIVE 로 올라간다.
    op.execute("LOCK TABLE stock_ledger_entries IN SHARE ROW EXCLUSIVE MODE")

    # **조이기 전에 묻는다**(감사 ㊸ OB-1). 창고마다 세면 음수가 되는 (로트, 창고) — 바뀐 잔량 트리거는
    # 그 창고에서 다음 줄을 받지 못하고, 그 줄이 왜 거기 섰는지는 사람만 안다.
    op.execute(
        """
        DO $$
        DECLARE short text;
        BEGIN
          SELECT string_agg(s.lot_number || ' ' || s.warehouse || '창고', ', '
                            ORDER BY s.lot_number, s.warehouse)
            INTO short
          FROM (
            SELECT l.lot_number, e.warehouse
            FROM stock_ledger_entries AS e
            JOIN lots AS l ON l.id = e.lot_id
            JOIN txn_type_attributes AS a
              ON a.group_code = e.txn_type_group AND a.code = e.txn_type
            GROUP BY l.id, l.lot_number, e.warehouse
            HAVING sum(CASE a.total_effect
                         WHEN '증가' THEN e.quantity::numeric
                         WHEN '감소' THEN -e.quantity::numeric
                       END) < 0
          ) AS s;
          IF short IS NOT NULL THEN
            RAISE EXCEPTION
              '창고마다 세면 잔량이 음수가 되는 로트가 있다: %. 잔량을 로트 하나로 세던 동안 들어온 적 없는 창고에서 나간 줄이라 사람이 먼저 가른다',
              short;
          END IF;
        END $$;
        """
    )
    # 0 짜리 폐기 줄 — 아래의 「0 은 폐기가 아니다」 CHECK 가 제약 이름만 내놓고 멈춘다.
    op.execute(
        """
        DO $$
        DECLARE empty text;
        BEGIN
          SELECT string_agg(DISTINCT l.lot_number, ', ' ORDER BY l.lot_number) INTO empty
          FROM stock_ledger_entries AS e
          JOIN lots AS l ON l.id = e.lot_id
          WHERE e.txn_type = '폐기출고' AND e.quantity = 0;
          IF empty IS NOT NULL THEN
            RAISE EXCEPTION
              '수량이 0 인 폐기 줄이 있는 로트가 있다: %. 폐기는 그 창고에 남은 것을 내보내는 줄이라 0 은 폐기가 아니므로 사람이 먼저 가른다',
              empty;
          END IF;
        END $$;
        """
    )

    # ── 표 둘 — 요청과 그 끝 ───────────────────────────────────────────────
    op.create_table(
        "stock_transfer_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("requested_by", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "quantity > 0 AND quantity > '-Infinity'::double precision AND quantity < 'Infinity'::double precision",
            name="ck_stock_transfer_request_quantity",
        ),
        sa.CheckConstraint(
            "btrim(requested_by, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_stock_transfer_request_requested_by_is_present",
        ),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], name="fk_stock_transfer_request_lot"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "lot_id",
            "quantity",
            "requested_at",
            name="uq_stock_transfer_request_closure_match",
        ),
    )
    op.create_table(
        "stock_transfer_closures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("closure_type", sa.String(length=10), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.Column("closed_by", sa.String(length=50), nullable=False),
        sa.CheckConstraint(
            "closure_type IN ('처리', '취소')", name="ck_stock_transfer_closure_type"
        ),
        sa.CheckConstraint(
            "closed_at >= requested_at", name="ck_stock_transfer_closure_after_the_request"
        ),
        sa.CheckConstraint(
            "btrim(closed_by, E' \\t\\n\\r\\u3000\\u00a0') <> ''",
            name="ck_stock_transfer_closure_closed_by_is_present",
        ),
        sa.ForeignKeyConstraint(
            ["request_id", "lot_id", "quantity", "requested_at"],
            [
                "stock_transfer_requests.id",
                "stock_transfer_requests.lot_id",
                "stock_transfer_requests.quantity",
                "stock_transfer_requests.requested_at",
            ],
            name="fk_stock_transfer_closure_request",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_stock_transfer_closure_request"),
        sa.UniqueConstraint(
            "id",
            "closure_type",
            "lot_id",
            "quantity",
            "closed_at",
            name="uq_stock_transfer_closure_ledger_match",
        ),
    )

    # ── 원장 — 이동 줄을 받고 폐기 줄을 창고마다 ───────────────────────────
    op.add_column(
        "stock_ledger_entries", sa.Column("transfer_closure_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "stock_ledger_entries",
        sa.Column("transfer_closure_type", sa.String(length=10), nullable=True),
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source",
        "stock_ledger_entries",
        "txn_type IN ('구매입고', '구매반품출고', '폐기출고', '생산출고', '생산입고')",
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse",
        "stock_ledger_entries",
        "(txn_type <> '구매입고' OR warehouse = '원재료') AND (txn_type <> '구매반품출고' OR warehouse = '원재료') AND (txn_type <> '생산출고' OR warehouse = '원재료') AND (txn_type <> '생산입고' OR warehouse = '생산')",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_disposal_takes_something",
        "stock_ledger_entries",
        "txn_type <> '폐기출고' OR quantity > 0",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_transfer_names_its_closure",
        "stock_ledger_entries",
        "(txn_type IN ('생산출고', '생산입고')) = (transfer_closure_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_transfer_follows_a_processing",
        "stock_ledger_entries",
        "(transfer_closure_id IS NULL) = (transfer_closure_type IS NULL) AND (transfer_closure_type IS NULL OR transfer_closure_type = '처리')",
    )
    op.create_foreign_key(
        "fk_stock_ledger_entry_transfer_closure",
        "stock_ledger_entries",
        "stock_transfer_closures",
        ["transfer_closure_id", "transfer_closure_type", "lot_id", "quantity", "occurred_at"],
        ["id", "closure_type", "lot_id", "quantity", "closed_at"],
    )
    op.create_index(
        "uq_stock_ledger_entry_one_line_per_transfer_side",
        "stock_ledger_entries",
        ["transfer_closure_id", "txn_type"],
        unique=True,
        postgresql_where=sa.text("transfer_closure_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_stock_ledger_entry_one_line_per_retest", table_name="stock_ledger_entries"
    )
    op.create_index(
        "uq_stock_ledger_entry_one_line_per_retest_warehouse",
        "stock_ledger_entries",
        ["retest_id", "warehouse"],
        unique=True,
        postgresql_where=sa.text("retest_id IS NOT NULL"),
    )

    for statement in (
        _LEDGER_GUARD_FUNCTION,
        _RETEST_LINE_FUNCTION,
        _TRANSFER_REQUEST_FUNCTION,
        _TRANSFER_REQUEST_TRIGGER,
        _TRANSFER_CLOSURE_FUNCTION,
        _TRANSFER_CLOSURE_TRIGGER,
        _TRANSFER_LINES_FUNCTION,
        _TRANSFER_LINES_TRIGGER,
    ):
        op.execute(statement)


def downgrade() -> None:
    # **세기 전에 잠근다** — 요청을 넣는 트랜잭션이 커밋되기 전에 세면 0 을 보고 지나가고, 뒤의 `DROP`
    # 이 그 트랜잭션을 기다렸다가 커밋된 요청째 표를 지운다.
    op.execute("LOCK TABLE stock_transfer_requests IN SHARE MODE")
    # **사라지는 것을 먼저 세고 멈춘다.** 누가 냈는지가 아니라 몇 건인지를 말한다 — 이 메시지는 서버
    # 로그에도 남는다(감사 ⑲ NC-173).
    op.execute(
        """
        DO $$
        DECLARE requested bigint;
        BEGIN
          SELECT count(*) INTO requested FROM stock_transfer_requests;
          IF requested > 0 THEN
            RAISE EXCEPTION
              '되돌리면 이동 요청 %건과 그 종결 · 원장 줄이 사라진다. 옮긴 물건이 원재료창고로 돌아온 것이 된다',
              requested;
          END IF;
        END $$;
        """
    )

    op.execute(
        "DROP TRIGGER stock_transfer_processing_has_its_ledger_lines ON stock_transfer_closures"
    )
    op.execute(
        "DROP TRIGGER stock_transfer_closure_moves_only_a_live_lot ON stock_transfer_closures"
    )
    op.execute(
        "DROP TRIGGER stock_transfer_request_comes_after_the_receipt ON stock_transfer_requests"
    )
    op.execute("DROP FUNCTION stock_transfer_processing_has_its_ledger_lines()")
    op.execute("DROP FUNCTION stock_transfer_closure_moves_only_a_live_lot()")
    op.execute("DROP FUNCTION stock_transfer_request_comes_after_the_receipt()")
    op.execute(_RETEST_LINE_FUNCTION_BEFORE)
    op.execute(_LEDGER_GUARD_FUNCTION_BEFORE)

    op.drop_index(
        "uq_stock_ledger_entry_one_line_per_retest_warehouse", table_name="stock_ledger_entries"
    )
    op.create_index(
        "uq_stock_ledger_entry_one_line_per_retest",
        "stock_ledger_entries",
        ["retest_id"],
        unique=True,
        postgresql_where=sa.text("retest_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_stock_ledger_entry_one_line_per_transfer_side", table_name="stock_ledger_entries"
    )
    op.drop_constraint(
        "fk_stock_ledger_entry_transfer_closure", "stock_ledger_entries", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_transfer_follows_a_processing",
        "stock_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_transfer_names_its_closure",
        "stock_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_disposal_takes_something", "stock_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_type_sets_warehouse",
        "stock_ledger_entries",
        "(txn_type <> '구매입고' OR warehouse = '원재료') AND (txn_type <> '구매반품출고' OR warehouse = '원재료')",
    )
    op.drop_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source", "stock_ledger_entries", type_="check"
    )
    op.create_check_constraint(
        "ck_stock_ledger_entry_txn_type_has_a_source",
        "stock_ledger_entries",
        "txn_type IN ('구매입고', '구매반품출고', '폐기출고')",
    )
    op.drop_column("stock_ledger_entries", "transfer_closure_type")
    op.drop_column("stock_ledger_entries", "transfer_closure_id")
    op.drop_table("stock_transfer_closures")
    op.drop_table("stock_transfer_requests")
