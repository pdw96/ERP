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
  단서 ②)
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
# **유형이 없거나 로트가 없으면 아무 말 없이 넘긴다.** 그 줄은 외래키가 거부하고,
# 거기서 나오는 말(제약 이름)이 더 정확하다. **셀 수 없는 수(`NaN` · 무한대)도
# 넘긴다** — 넘기지 않으면 합이 `NaN` 이나 무한대가 되어 트리거가 엉뚱한 말(「잔량이
# 음수다」)로 거부하고, 그 줄의 진짜 이유는 `is_finite()` CHECK 가 말한다.
LEDGER_GUARD_FUNCTION = f"""
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
  FROM lots WHERE id = NEW.lot_id FOR UPDATE;
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
  WHERE group_code = NEW.txn_type_group AND code = NEW.txn_type;
  IF NOT FOUND THEN
    RETURN NEW;
  END IF;
  IF effect NOT IN ('{codes.EFFECT_INCREASE}', '{codes.EFFECT_DECREASE}') THEN
    RAISE EXCEPTION '총량 영향이 「%」인 유형(%)은 잔량을 셀 수 없다', effect, NEW.txn_type
      USING ERRCODE = 'check_violation';
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

# ── 반품 문서 — 불합격분의 합 · 고치지 않는다 ───────────────────────────────
#
# **재고 로트 반품은 원장이 지킨다** — 반품 한 줄마다 원장에 구매반품출고 한 줄이 서고
# 위의 잔량 트리거가 그 줄을 본다. **불합격분 반품은 원장 줄이 없으므로**(재고가 된 적이
# 없다) 같은 합의 규칙을 여기서 건다: 한 불합격 검사에서 돌려보낸 수량의 합이 그 검사가
# 받은 수량을 넘지 않는다. 잠그는 것은 그 검사 줄이다.
RETURN_GUARD_FUNCTION = f"""
CREATE OR REPLACE FUNCTION purchase_return_stays_within_what_came() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  received double precision;
  returned numeric;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION '반품 문서는 고치거나 지우지 않는다 — 일어난 일이다 (반품 %)', OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;

  IF NOT (NEW.quantity > '-Infinity' AND NEW.quantity < 'Infinity') THEN
    RETURN NEW;
  END IF;

  IF NEW.lot_id IS NOT NULL THEN
    RETURN NEW;
  END IF;

  SELECT quantity INTO received FROM inspections
  WHERE id = NEW.inspection_id AND result = '{codes.JUDGMENT_FAILED}' FOR UPDATE;
  IF NOT FOUND THEN
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


def _run(*statements: str) -> Callable[..., None]:
    def listener(target: FromClause, connection: Connection, **_: object) -> None:
        for statement in statements:
            connection.execute(text(statement))

    return listener


def install(*, ledger: FromClause, returns: FromClause) -> None:
    """표가 설 때 트리거도 서게 한다 — `create_all` 이 메타데이터 밖의 것을 모르므로.

    **원장이 선 뒤에 로트 트리거를 건다.** 로트 쪽 함수가 원장을 읽고, `create_all` 은
    외래키 순서대로 세우므로 원장이 설 때 로트는 이미 있다.
    """
    event.listen(
        ledger,
        "after_create",
        _run(
            LEDGER_GUARD_FUNCTION,
            LEDGER_GUARD_TRIGGER,
            LOT_QUANTITY_FUNCTION,
            LOT_QUANTITY_TRIGGER,
        ),
    )
    event.listen(returns, "after_create", _run(RETURN_GUARD_FUNCTION, RETURN_GUARD_TRIGGER))
