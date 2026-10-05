"""원장 줄의 창고 — 4단계 조각 2 (ADR 0022).

**로트는 하나여도 창고는 줄마다다.** 원장 줄이 그 줄이 일어난 창고와 품목 유형을 들고, 그 창고가
그 품목을 담을 수 있는지 · 유형이 정하는 창고에 섰는지 · 입고 줄이 로트의 들어온 창고와 같은지를
데이터베이스가 본다. 로트의 들어온 창고는 원장에 줄이 선 뒤에 움직이지 않는다.

잔량을 창고별로 세는 것과 나뉜 로트를 창고마다 폐기하는 것은 이동이 서는 조각의 일이다(저장소
소유자, 2026-10-05) — 이동이 없으면 로트가 한 창고에만 있어 그 둘이 드러나지 않는다.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.inspection import Inspection
from app.db.inventory import StockLedgerEntry
from app.db.master import Item
from tests import test_purchase_returns as returns_case
from tests import test_retest as retest_case


@pytest.fixture
def expired(session: Session) -> Session:
    """만료된 로트 하나(500, 입고 줄까지) — 재검사와 폐기 줄을 세울 자리."""
    retest_case._plant(session)
    return session


@pytest.fixture
def returned(session: Session) -> Session:
    """합격한 로트 하나(500, 입고 줄까지) — 반품 문서와 그 줄을 세울 자리."""
    returns_case._plant(session)
    return session


def _failed_retest(session: Session) -> Inspection:
    retest = retest_case._retest(session, codes.JUDGMENT_FAILED)
    retest_case._add(session, retest)
    return retest


# ── 창고가 담는 품목 ─────────────────────────────────────────────────────────
# 폐기 줄로 잰다 — 창고를 고르지 않는 유형이라 「유형이 정하는 창고」 CHECK 와 입고 줄의
# 트리거가 함께 나서지 않는다.


def test_a_line_stands_only_in_a_warehouse_that_exists(expired: Session) -> None:
    """창고는 셋 가운데 하나다 — `lots` 와 같은 목록."""
    retest = _failed_retest(expired)
    with pytest.raises(IntegrityError, match=r"ck_stock_ledger_entry_warehouse\b"):
        retest_case._add(expired, retest_case._disposal(expired, retest, warehouse="창고"))


def test_a_line_stands_only_in_a_warehouse_that_holds_its_item(expired: Session) -> None:
    """**제품창고는 원자재를 담지 않는다** — `lots` 의 「창고가 담는 품목 유형」이 줄에도
    걸린다."""
    retest = _failed_retest(expired)
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_warehouse_holds_type"):
        retest_case._add(
            expired,
            retest_case._disposal(expired, retest, warehouse=codes.WAREHOUSE_FINISHED),
        )


def test_a_line_takes_its_item_type_from_its_lot(expired: Session) -> None:
    """**유형은 로트에서 끌어온다** — 원자재 로트의 줄이 반제품이라고 적으면 생산창고가 그것을
    담을 수 있어 CHECK 는 지나가지만, 쌍 외래키가 로트의 유형과 견주어 막는다."""
    retest = _failed_retest(expired)
    with pytest.raises(IntegrityError, match="fk_stock_ledger_entry_lot_type"):
        retest_case._add(
            expired,
            retest_case._disposal(
                expired,
                retest,
                warehouse=codes.WAREHOUSE_PRODUCTION,
                item_type=codes.SEMI_FINISHED,
            ),
        )


# ── 유형이 정하는 창고 ───────────────────────────────────────────────────────


def test_a_receipt_comes_into_the_raw_warehouse(expired: Session) -> None:
    """**사 온 물건은 원재료창고로 들어온다** — 원자재 로트는 생산창고에도 설 수 있지만, 그
    로트에 입고 줄을 세우면 「유형이 정하는 창고」가 막는다. 로트의 창고와 같은 줄이라 입고 줄의
    트리거는 지나간다 — 막는 것은 이 CHECK 하나다."""
    material = expired.query(Item).one()
    lot = retest_case._a_lot(expired, material, "RM-01-260921-02", None, receipt=False)
    # 원장에 줄이 없는 로트의 창고는 고칠 수 있다 — 굳히는 트리거는 줄이 선 뒤에만 걸린다
    lot.warehouse = codes.WAREHOUSE_PRODUCTION
    expired.flush()

    expired.add(
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=codes.TXN_PURCHASE_RECEIPT,
            warehouse=codes.WAREHOUSE_PRODUCTION,
            item_type=lot.item_type,
            quantity=lot.quantity,
            occurred_at=retest_case.JUDGED,
        )
    )
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_type_sets_warehouse"):
        expired.flush()


def test_a_return_leaves_from_the_raw_warehouse(returned: Session) -> None:
    """**반품은 원재료창고에서만 나간다**(저장소 소유자, 2026-10-05) — 생산창고로 옮긴 분량은
    공급사에 돌려보내지 않는다."""
    document = returns_case._lot_return(returned, 100.0)
    returned.add(document)
    returned.flush()

    returned.add(returns_case._return_line(document, warehouse=codes.WAREHOUSE_PRODUCTION))
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_type_sets_warehouse"):
        returned.flush()


# ── 입고 줄과 로트의 들어온 창고 ─────────────────────────────────────────────


def test_a_receipt_stands_in_the_warehouse_its_lot_came_into(expired: Session) -> None:
    """**입고 줄의 창고는 그 로트의 들어온 창고다** — 둘이 갈리면 로트와 원장이 서로 다른
    곳으로 들어왔다고 말한다. 원재료창고로 들어온 로트의 입고 줄을 생산창고에 세우면 트리거가
    막는다."""
    material = expired.query(Item).one()
    lot = retest_case._a_lot(expired, material, "RM-01-260921-02", None, receipt=False)

    expired.add(
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=codes.TXN_PURCHASE_RECEIPT,
            warehouse=codes.WAREHOUSE_PRODUCTION,
            item_type=lot.item_type,
            quantity=lot.quantity,
            occurred_at=retest_case.JUDGED,
        )
    )
    with pytest.raises(DBAPIError, match="입고 줄의 창고\\(생산\\)가 로트 RM-01-260921-02"):
        expired.flush()


def test_the_warehouse_a_lot_came_into_stays_once_its_ledger_has_a_line(
    expired: Session,
) -> None:
    """**들어온 창고는 지나간 사실이다** — 원장에 줄이 선 로트의 `warehouse` 를 고치면 고칠 수
    없는 입고 줄의 창고와 갈린다."""
    lot = retest_case._the_lot(expired)
    with pytest.raises(DBAPIError, match="들어온 창고는 원장에 줄이 선 뒤에 고치지 않는다"):
        expired.execute(
            text("UPDATE lots SET warehouse = :to WHERE id = :lot"),
            {"to": codes.WAREHOUSE_PRODUCTION, "lot": lot.id},
        )


def test_the_frozen_warehouse_does_not_hold_back_other_columns(expired: Session) -> None:
    """**굳히는 것은 창고 칸 하나다** — 같은 값으로 쓰는 갱신과 다른 칸의 갱신은 지나간다."""
    lot = retest_case._the_lot(expired)
    expired.execute(
        text(
            "UPDATE lots SET warehouse = warehouse, passed_date = passed_date WHERE id = :lot"
        ),
        {"lot": lot.id},
    )
    expired.refresh(lot)
    assert lot.warehouse == codes.WAREHOUSE_RAW
