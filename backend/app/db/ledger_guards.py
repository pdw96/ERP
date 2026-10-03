"""원장의 합을 지키는 트리거 — **CHECK 로 적을 수 없는 규칙**(ADR 0013).

「한 로트의 원장 줄을 합한 잔량이 0 밑으로 내려가지 않는다」는 줄 하나가 아니라
**여러 줄의 합**에 대한 규칙이다. CHECK 는 자기 줄만 보고, 외래키는 같음만 본다.
쓰기 경로가 지키게 두면 「쓰는 코드가 하나뿐이라 갈리지 않는다」 — 대장의 NC-70 이
**제약이 아니라 우연**이라 부른 상태가 남는다. 그래서 데이터베이스가 건다.

**모델과 마이그레이션이 같은 글자를 쓴다.** 모델 쪽은 표가 설 때 이 SQL 을 부르고
(`install()`), 마이그레이션은 같은 SQL 을 그 리비전에 굳혀 둔다. 둘이 갈리면
`tests/test_migrations.py` 가 함수와 트리거의 **정의**를 견주어 잡는다 — 메타데이터에는
트리거가 없으므로 칸과 제약을 견주는 것만으로는 보이지 않는다.

**이 트리거들이 못 보는 부류**(W-6 ③) —

- `TRUNCATE` — 줄 단위 트리거를 부르지 않는다. 표를 통째로 비우는 것은 줄의 사실을
  고치는 것이 아니라 표를 버리는 것이고, 그 권한은 데이터베이스 소유자의 일이다
- `session_replication_role = replica` 로 트리거를 끄고 넣는 길 — 같은 권한의 일이다.
  단일 사용자 로컬 Compose 에서는 그 권한을 가르지 않으며, 배포처가 생기는 날 권한
  경계와 함께 다시 본다(ADR 0013 「결과」)
- **로트는 생겼는데 입고 줄이 없는 상태** — 줄이 들어올 때 부르는 트리거는 들어오지
  않은 줄을 볼 수 없다. 쓰기 경로가 한 트랜잭션으로 지킨다(`docs/PRD-2단계.md` 「닫으며」의
  단서 ②). 반품 쪽의 같은 자리(문서는 섰는데 원장 줄이 없다)는 아래 지연 트리거가 커밋
  시점에 막는다 — 입고 쪽에 같은 것을 걸지 못하는 것은 기초재고 로트를 가를 표식이 아직
  없어서다

**합이 기대는 다른 표의 값도 고정한다**(감사 ㉟ NC-223). 줄이 들어오는 순간만 보는 트리거는
그 뒤에 분모가 움직이면 모른다 — 로트 수량(`lot_quantity_stays_with_its_ledger`), 유형의
총량 영향(`txn_type_effect_stays_behind_its_lines`), 반품이 가리키는 검사의 수량 · 공급사 ·
품목 · 시각(`inspection_stays_behind_its_returns`)을 각각 지킨다.

**재검사도 같은 자리다**(3단계 재검사, ADR 0016). 「만료된 로트만 재검사를 받는다」는
로트의 지금 만료일 — 다른 표의 여러 줄 — 을 보는 조건이라 CHECK 로 적을 수 없다. 들어오는
순간 묻는 트리거와, 그 규칙이 읽는 것(재검사 줄 · 검사 단계 · 로트의 만료일)을 고정하는
트리거가 이 파일 뒤쪽에 있다.

**잠금은 `FOR NO KEY UPDATE` 다**(Codex 리뷰 · 감사 ㉟ OB-1). 반품 문서를 넣을 때 외래키
검사가 로트 · 검사 줄에 `KEY SHARE` 를 잡는데, `FOR UPDATE` 는 그것과 부딪쳐 「문서 먼저,
원장 줄 나중」인 두 트랜잭션이 서로를 기다리다 교착으로 끊겼다. `NO KEY UPDATE` 끼리는 줄을
세우고 `KEY SHARE` 와는 부딪치지 않는다.
"""

from collections.abc import Callable

from sqlalchemy import Connection, FromClause, event, text

from app.core import codes

# ── 원장 — 잔량 · 입고 수량 · 고치지 않는다 ─────────────────────────────────
#
# **합은 `numeric` 으로 센다.** `double precision` 으로 더하면 100 − 33.3 − 66.7 이
# 0 이 아니라 −1.4e-14 쯤이 되고, 실제로는 다 빠진 로트를 「음수」라며 거부한다.
# 값을 넣을 때 쓰던 자릿수(15 자리)로 옮겨 더하면 사람이 넣은 수끼리의 합이 맞는다.
#
# **로트 줄을 잠근다.** 잠그지 않으면 두 반품이 같은 잔량을 보고 함께 통과한다 —
# `READ COMMITTED` 에서 트리거 안의 각 문장은 새 스냅숏을 받으므로, 잠금을 얻은 뒤의
# 합은 앞서 커밋된 줄을 본다.
#
# **유형 속성 줄을 `FOR SHARE` 로 읽는다**(Codex 리뷰 2 라운드). 그 유형의 첫 줄이 커밋되기 전에
# 방향을 바꾸는 갱신이 끼면, 고정 트리거는 「아직 줄이 없다」를 보고 통과시키고 이 트리거는 옛
# 방향으로 셌다 — 둘 다 커밋되면 새 줄이 바뀐 방향으로 읽힌다. `FOR SHARE` 는 그 갱신이 잡는
# `NO KEY UPDATE` 와 부딪쳐 갱신을 이 줄의 커밋 뒤로 세우고, 그때 고정 트리거가 줄을 본다.
# 줄끼리는 `FOR SHARE` 가 서로 부딪치지 않는다.
#
# **유형의 방향은 `codes.LEDGER_EFFECTS` 와 견준다**(Codex 리뷰 4 라운드). 아래의 고정
# 트리거는 줄이 선 유형만 지키므로, 아직 줄이 없는 유형이 거꾸로 고쳐져 있으면 첫 줄이
# 잔량을 거꾸로 세고 곧바로 그 방향을 고정한다. 목록에 없는 유형은 넘긴다 — 원장 CHECK 가
# 같은 목록으로 거부하고 그 이름이 더 정확하다.
#
# **나가는 줄의 시각은 입고 줄과 견준다**(Codex 리뷰 4 라운드). 반품 문서의 트리거도
# 견주지만, 입고 줄이 아직 없는 로트에서는 견줄 것이 없어 지나간다 — 같은 트랜잭션에서 늦은
# 입고 줄을 넣고 반품 줄을 마지막에 넣으면 합도 지연 트리거도 통과한다. 입고 줄이 없으면 이
# 비교는 지나가지만, 그때는 잔량이 0 이라 나가는 줄이 바로 아래에서 막힌다.
#
# **폐기 줄은 잔량 전부다**(3단계 재검사). 재검사에서 떨어진 로트는 한 줄로 0 이 된다 —
# 일부만 버리면 떨어진 물건이 재고에 남는다. 폐기 줄은 재검사만 가리키고 양을 들지 않으므로
# (재검사는 로트를 통째로 본다) 그 양이 맞는지는 합을 세는 이 자리가 본다.
#
# **유형이 없거나 로트가 없으면 아무 말 없이 넘긴다.** 그 줄은 외래키가 거부하고,
# 거기서 나오는 말(제약 이름)이 더 정확하다. **셀 수 없는 수(`NaN` · 무한대)도
# 넘긴다** — 넘기지 않으면 합이 `NaN` 이나 무한대가 되어 트리거가 엉뚱한 말(「잔량이
# 음수다」)로 거부하고, 그 줄의 진짜 이유는 `is_finite()` CHECK 가 말한다.
_EXPECTED_EFFECTS = " ".join(
    f"WHEN '{txn_type}' THEN '{effect}'" for txn_type, effect in codes.LEDGER_EFFECTS.items()
)

LEDGER_GUARD_FUNCTION = f"""
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

  IF NEW.txn_type = '{codes.TXN_PURCHASE_RECEIPT}'
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
  expected := CASE NEW.txn_type {_EXPECTED_EFFECTS} END;
  IF expected IS NULL THEN
    RETURN NEW;
  END IF;
  IF effect IS DISTINCT FROM expected THEN
    RAISE EXCEPTION '유형 %의 총량 영향이 「%」로 서 있다 — 원장은 이 유형을 「%」으로 센다',
      NEW.txn_type, effect, expected
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type <> '{codes.TXN_PURCHASE_RECEIPT}' THEN
    SELECT occurred_at INTO came_in FROM stock_ledger_entries
    WHERE lot_id = NEW.lot_id AND txn_type = '{codes.TXN_PURCHASE_RECEIPT}';
    IF NEW.occurred_at < came_in THEN
      RAISE EXCEPTION
        '줄의 시각(%)이 로트 %의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
        NEW.occurred_at, lot_label, came_in
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;

  SELECT coalesce(sum(CASE a.total_effect
                        WHEN '{codes.EFFECT_INCREASE}' THEN e.quantity::numeric
                        WHEN '{codes.EFFECT_DECREASE}' THEN -e.quantity::numeric
                      END), 0)
    INTO balance
  FROM stock_ledger_entries AS e
  JOIN txn_type_attributes AS a ON a.group_code = e.txn_type_group AND a.code = e.txn_type
  WHERE e.lot_id = NEW.lot_id;

  IF effect = '{codes.EFFECT_INCREASE}' THEN
    balance := balance + NEW.quantity::numeric;
  ELSE
    balance := balance - NEW.quantity::numeric;
  END IF;

  IF balance < 0 THEN
    RAISE EXCEPTION '로트 %의 잔량이 %이 된다 — 있는 것보다 많이 뺄 수 없다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  IF NEW.txn_type = '{codes.TXN_DISPOSAL}' AND balance <> 0 THEN
    RAISE EXCEPTION '폐기출고는 로트 %의 잔량 전부다 — %이 남는다', lot_label, balance
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END $$
"""

LEDGER_GUARD_TRIGGER = """
CREATE TRIGGER stock_ledger_entry_keeps_the_balance
BEFORE INSERT OR UPDATE OR DELETE ON stock_ledger_entries
FOR EACH ROW EXECUTE FUNCTION stock_ledger_entry_keeps_the_balance()
"""

# ── 로트 — 원장이 선 뒤에는 수량이 움직이지 않는다 ──────────────────────────
#
# **입고 줄과 로트 수량이 같다는 것은 두 쪽에서 지켜야 한다.** 원장 쪽 트리거는 줄이
# 들어오는 순간만 보므로, 그 뒤에 로트의 수량을 고치면 둘이 다시 갈린다. 원장에 줄이
# 없는 로트(기초재고 · 아직 입고 줄이 서기 전)는 막지 않는다.
LOT_QUANTITY_FUNCTION = """
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

LOT_QUANTITY_TRIGGER = """
CREATE TRIGGER lot_quantity_stays_with_its_ledger
BEFORE UPDATE OF quantity ON lots
FOR EACH ROW EXECUTE FUNCTION lot_quantity_stays_with_its_ledger()
"""

# ── 유형 — 원장이 선 뒤에는 방향이 움직이지 않는다 ──────────────────────────
#
# **잔량의 부호는 이 칸이 말한다.** 원장 줄이 선 뒤에 「구매반품출고」를 「증가」로 고치면
# 지나간 반품이 전부 재고를 늘린 것으로 다시 세어지고, 「불변」으로 고치면 그 유형의
# 줄이 합에서 사라져 정상 로트의 다음 반품이 거부된다. 줄이 없는 유형은 고칠 수 있다.
EFFECT_FUNCTION = """
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

EFFECT_TRIGGER = """
CREATE TRIGGER txn_type_effect_stays_behind_its_lines
BEFORE UPDATE OF total_effect ON txn_type_attributes
FOR EACH ROW EXECUTE FUNCTION txn_type_effect_stays_behind_its_lines()
"""

# ── 반품 문서 — 시각 · 불합격분의 합 · 고치지 않는다 ────────────────────────
#
# **재고 로트 반품은 원장이 지킨다** — 반품 한 줄마다 원장에 구매반품출고 한 줄이 서고
# 위의 잔량 트리거가 그 줄을 본다. **불합격분 반품은 원장 줄이 없으므로**(재고가 된 적이
# 없다) 같은 합의 규칙을 여기서 건다: 한 불합격 검사에서 돌려보낸 수량의 합이 그 검사가
# 받은 수량을 넘지 않는다.
#
# **판정보다 앞선 반품은 없다**(Codex 리뷰). 들어와 판정받기 전의 물건은 돌려보낼 수 없다 —
# 도착일은 판정일보다 늦을 수 없으므로(`ck_inspection_judged_after_arrival`) 판정 시각
# 하나로 둘 다 지켜진다. **재고 로트는 입고 줄의 시각과도 견준다**(Codex 리뷰 2 라운드) —
# 쓰기 경로는 입고 시각을 판정 시각으로 적지만, 그것을 묶는 제약은 없어 입고가 판정보다 늦은
# 줄이 설 수 있다. 입고 줄이 아직 없는 로트는 여기서 견줄 것이 없으므로, 반품 줄이 들어올 때
# 잔량 트리거가 다시 견준다(Codex 리뷰 4 라운드).
#
# **잠그는 것은 그 검사 줄이다** — 반품이 가리키는 쪽이 하나뿐이라 갈래마다 같다.
RETURN_GUARD_FUNCTION = f"""
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
    WHERE lot_id = NEW.lot_id AND txn_type = '{codes.TXN_PURCHASE_RECEIPT}';
    IF NEW.returned_at < came_in THEN
      RAISE EXCEPTION
        '반품 시각(%)이 그 로트의 입고 시각(%)보다 앞선다 — 들어오기 전의 물건이다',
        NEW.returned_at, came_in
        USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
  END IF;

  IF judged_result <> '{codes.JUDGMENT_FAILED}' THEN
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

RETURN_GUARD_TRIGGER = """
CREATE TRIGGER purchase_return_stays_within_what_came
BEFORE INSERT OR UPDATE OR DELETE ON purchase_returns
FOR EACH ROW EXECUTE FUNCTION purchase_return_stays_within_what_came()
"""

# ── 반품 문서 → 원장 줄 — 커밋 시점에 묻는다 ───────────────────────────────
#
# **원장 쪽 제약은 줄 → 문서 방향만 본다**(감사 ㉟ NC-222 · Codex 리뷰 P1). 재고 로트를
# 돌려보낸 문서가 원장 줄 없이 홀로 서면, 공급사에게 간 물건이 잔량에서 빠지지 않는다 —
# 재고가 조용히 실물보다 많다. 문서와 줄은 한 트랜잭션에 서므로 **커밋할 때** 묻는다
# (`DEFERRABLE INITIALLY DEFERRED`). 문서를 먼저 넣고 줄을 나중에 넣는 순서가 그래서 선다.
RETURN_LINE_FUNCTION = """
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

RETURN_LINE_TRIGGER = """
CREATE CONSTRAINT TRIGGER purchase_return_has_its_ledger_line
AFTER INSERT ON purchase_returns
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION purchase_return_has_its_ledger_line()
"""

# ── 검사 — 반품이 가리키는 동안 움직이지 않는다 ─────────────────────────────
#
# **반품 문서는 공급사 · 품목을 검사에서 따라간다**(칸을 두지 않았다). 그러니 반품이 선 뒤에
# 검사의 공급사를 고치면 그 반품이 다른 공급사로 간 것이 되고, 수량을 고치면 불합격분의 합
# 규칙이 기대는 분모가 움직이며, 판정 시각을 고치면 위의 시각 규칙이 비켜 간다(감사 ㉟ NC-223 ·
# Codex 리뷰).
#
# **칸을 골라 고정하지 않고 줄을 통째로 고정한다.** 처음에는 수량 · 공급사 · 품목 ·
# 시각을, 2 라운드에 사유를, 3 라운드에 공급사 로트번호를 더하라는 지적이 차례로 났다 —
# 반품 문서가 검사에서 따라가는 칸은 결국 검사 줄 전부다(불합격분은 로트가 없어 공급사의
# 배치도 검사가 든다). 판정 기록을 반품 뒤에 고칠 정당한 경로가 없으므로 어느 칸이든
# 바뀌면 거부한다.
INSPECTION_FUNCTION = """
CREATE OR REPLACE FUNCTION inspection_stays_behind_its_returns() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW IS DISTINCT FROM OLD
     AND EXISTS (SELECT 1 FROM purchase_returns WHERE inspection_id = OLD.id) THEN
    RAISE EXCEPTION
      '검사 %를 반품이 가리킨다 — 그 판정 기록은 어느 칸도 고치지 않는다',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

INSPECTION_TRIGGER = """
CREATE TRIGGER inspection_stays_behind_its_returns
BEFORE UPDATE ON inspections
FOR EACH ROW EXECUTE FUNCTION inspection_stays_behind_its_returns()
"""

# ── 재검사 — 만료된 로트에만, 들어오는 순간 한 번 묻는다 (ADR 0016) ────────────
#
# **「만료」는 재검사 줄 하나로 가를 수 없다.** 로트의 지금 만료일은 「가장 최근에 합격한
# 재검사의 갱신 만료일, 없으면 `lots.expiry_date`」이고 그것을 판정일과 견준다 — 다른 표의
# 여러 줄을 보는 조건이라 CHECK 로 적을 수 없다.
#
# **경계: 만료일 당일까지는 쓸 수 있다.** 지금 만료일이 판정일보다 **앞설 때만** 만료다. IQC
# 쓰기 경로가 「이미 지난 자재」를 `만료일 < 판정일` 로 가른 것과 같은 경계이고, 갱신 만료일의
# CHECK(`ck_inspection_renewal_after_judgement`)도 같은 경계를 쓴다.
#
# **로트 줄을 잠근 뒤에 묻는다** — 같은 로트의 두 재검사가 함께 「만료」를 보고 서지 않게.
# 잠금은 `FOR NO KEY UPDATE` 다: 재검사 줄을 넣을 때 외래키 검사가 로트에 `KEY SHARE` 를
# 잡는데, `FOR UPDATE` 는 그것과 부딪친다(ADR 0013 이 겪은 교착).
#
# **묻는 것은 ADR 0016 의 원칙이 고르는 것이다** — 고정할 수 없는 것(잔량 · 앞선 불합격)은
# 같은 잠금 아래에서 묻는다.
#
# - **앞선 불합격 재검사가 있으면 거절한다.** 불합격은 잔량 전부를 폐기하는데, 그 줄이 같은
#   트랜잭션에서 아직 서기 전이면 잔량이 그대로 보인다 — 잠금은 같은 트랜잭션 안에서 다시
#   잡혀 막지 못한다
# - **앞선 재검사보다 이른 판정은 거절한다.** 「가장 최근」이 판정 시각의 순서이므로, 끼워
#   넣으면 지금 만료일이 어느 시점의 것인지 갈린다
# - **지금 만료일이 없으면(NULL) 만료가 아니다** — SQL 의 NULL 견줌은 막지 못하므로 따로 묻는다
# - **잔량이 0 보다 커야 한다** — 없는 물건을 검사한 기록이 된다
#
# **`BEFORE INSERT` 다.** `AFTER` 면 방금 넣은 합격 재검사의 갱신 만료일이 「가장 최근」으로
# 잡혀 정상 재검사가 전부 거절된다. 로트가 없으면 넘긴다 — 외래키 · CHECK 가 더 정확한 말로
# 거부한다.
RETEST_ADMISSION_FUNCTION = f"""
CREATE OR REPLACE FUNCTION retest_comes_only_to_an_expired_lot() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  lot_label text;
  labelled date;
  expires date;
  latest timestamp;
  balance numeric;
BEGIN
  IF NEW.inspection_stage <> '{codes.RETEST_STAGE}' OR NEW.target_lot_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT lot_number, expiry_date INTO lot_label, labelled
  FROM lots WHERE id = NEW.target_lot_id FOR NO KEY UPDATE;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;

  IF EXISTS (SELECT 1 FROM inspections
             WHERE target_lot_id = NEW.target_lot_id
               AND result = '{codes.JUDGMENT_FAILED}') THEN
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
  WHERE target_lot_id = NEW.target_lot_id AND result = '{codes.JUDGMENT_PASSED}'
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
                        WHEN '{codes.EFFECT_INCREASE}' THEN e.quantity::numeric
                        WHEN '{codes.EFFECT_DECREASE}' THEN -e.quantity::numeric
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

RETEST_ADMISSION_TRIGGER = """
CREATE TRIGGER retest_comes_only_to_an_expired_lot
BEFORE INSERT ON inspections
FOR EACH ROW EXECUTE FUNCTION retest_comes_only_to_an_expired_lot()
"""

# ── 검사 — 단계는 바뀌지 않고, 재검사는 고치지도 지우지도 않는다 ────────────
#
# **규칙이 읽는 줄은 고정한다**(ADR 0016). 재검사 줄의 로트 · 판정 시각을 고치면 만료되지 않은
# 로트로 옮겨 가고, 합격 재검사를 지우면 지금 만료일이 기준 만료일로 되돌아가 갱신된 로트가
# 다시 재검사를 받는다. 판정 기록을 고칠 정당한 경로가 아직 없다.
#
# **단계는 어느 줄에서도 바뀌지 않는다.** 재검사 줄만 고정하면 IQC 줄을 UPDATE 로 재검사로
# 바꾸며 칸을 한꺼번에 갈아 끼울 수 있다 — `OLD` 가 재검사가 아니라 위의 고정이 물지 않고,
# 들어오는 순간 묻는 트리거는 `INSERT` 에만 돈다.
INSPECTION_STAGE_FUNCTION = f"""
CREATE OR REPLACE FUNCTION inspection_keeps_its_stage() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.inspection_stage = '{codes.RETEST_STAGE}' THEN
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
  IF OLD.inspection_stage = '{codes.RETEST_STAGE}' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION '재검사 %는 고치지 않는다 — 그 로트의 지금 만료일이 그 위에 서 있다',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END $$
"""

INSPECTION_STAGE_TRIGGER = """
CREATE TRIGGER inspection_keeps_its_stage
BEFORE UPDATE OR DELETE ON inspections
FOR EACH ROW EXECUTE FUNCTION inspection_keeps_its_stage()
"""

# ── 로트 — 기준 만료일은 고치지 않는다 ─────────────────────────────────────
#
# **라벨에 찍혀 나간 값이다**(`PRD.md` 성공 기준 5). 재검사가 이 값을 읽으므로, 잠깐 과거로
# 돌려 재검사를 넣고 되돌리거나 앞으로 밀어 이미 선 재검사를 소급해 무효로 만들 수 있다.
# 원장에 줄이 있든 없든 막는다 — 고칠 까닭이 없다.
LOT_EXPIRY_FUNCTION = """
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

LOT_EXPIRY_TRIGGER = """
CREATE TRIGGER lot_expiry_stays_as_labelled
BEFORE UPDATE OF expiry_date ON lots
FOR EACH ROW EXECUTE FUNCTION lot_expiry_stays_as_labelled()
"""

# ── 재검사 불합격 → 폐기 줄 — 커밋 시점에 묻는다 ───────────────────────────
#
# **원장 쪽 외래키는 줄 → 재검사 방향만 본다.** 떨어진 재검사가 폐기 줄 없이 홀로 서면
# 떨어진 물건이 잔량에 남는다 — 반품 문서와 그 원장 줄의 자리
# (`purchase_return_has_its_ledger_line`)와 같다. 재검사는 잔량이 있는 로트에만 서므로(위의
# 트리거) 폐기할 것이 언제나 있다.
RETEST_LINE_FUNCTION = f"""
CREATE OR REPLACE FUNCTION retest_failure_has_its_disposal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.inspection_stage = '{codes.RETEST_STAGE}'
     AND NEW.result = '{codes.JUDGMENT_FAILED}'
     AND NOT EXISTS (SELECT 1 FROM stock_ledger_entries WHERE retest_id = NEW.id) THEN
    RAISE EXCEPTION
      '재검사 %는 로트를 떨어뜨렸는데 원장에 폐기 줄이 없다 — 판정과 폐기는 함께 선다',
      NEW.id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$
"""

RETEST_LINE_TRIGGER = """
CREATE CONSTRAINT TRIGGER retest_failure_has_its_disposal_line
AFTER INSERT ON inspections
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION retest_failure_has_its_disposal_line()
"""


def _run(*statements: str) -> Callable[..., None]:
    def listener(target: FromClause, connection: Connection, **_: object) -> None:
        for statement in statements:
            connection.execute(text(statement))

    return listener


def install(*, ledger: FromClause, returns: FromClause) -> None:
    """표가 설 때 트리거도 서게 한다 — `create_all` 이 메타데이터 밖의 것을 모르므로.

    **가리켜지는 표 위의 트리거는 가리키는 표가 설 때 건다.** `create_all` 은 외래키
    순서대로 세우므로, 원장이 설 때 로트 · 유형 속성 · 검사 표가, 반품 문서가 설 때 검사 표가
    이미 있다. 함수 본문이 읽는 다른 표는 부를 때 찾으므로 순서를 타지 않는다.
    """
    event.listen(
        ledger,
        "after_create",
        _run(
            LEDGER_GUARD_FUNCTION,
            LEDGER_GUARD_TRIGGER,
            LOT_QUANTITY_FUNCTION,
            LOT_QUANTITY_TRIGGER,
            EFFECT_FUNCTION,
            EFFECT_TRIGGER,
            RETEST_ADMISSION_FUNCTION,
            RETEST_ADMISSION_TRIGGER,
            INSPECTION_STAGE_FUNCTION,
            INSPECTION_STAGE_TRIGGER,
            LOT_EXPIRY_FUNCTION,
            LOT_EXPIRY_TRIGGER,
            RETEST_LINE_FUNCTION,
            RETEST_LINE_TRIGGER,
        ),
    )
    event.listen(
        returns,
        "after_create",
        _run(
            RETURN_GUARD_FUNCTION,
            RETURN_GUARD_TRIGGER,
            RETURN_LINE_FUNCTION,
            RETURN_LINE_TRIGGER,
            INSPECTION_FUNCTION,
            INSPECTION_TRIGGER,
        ),
    )
