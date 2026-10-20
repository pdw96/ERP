"""이동 — 4단계 조각 3 (이동)의 데이터베이스 쪽 (ADR 0022 · 0023).

**원재료창고의 로트를 요청과 처리로 생산창고에 옮긴다.** 요청은 의도라 재고를 잡지 않고, 처리는
종결 한 줄과 원장 두 줄(원재료창고의 생산출고 · 생산창고의 생산입고)이 한 트랜잭션이다. 취소는
새 사실이고 원장을 건드리지 않는다. 같은 로트가 두 창고에 나뉘므로 **잔량은 로트 × 창고로**
세고, 나뉜 로트가 재검사에서 떨어지면 잔량이 남은 창고마다 폐기 줄이 선다.

쓰기 경로가 서기 전이라 줄은 전부 직접 넣는다 — 쓰기 경로를 거치지 않아도 데이터베이스가 같은
거절을 내는지 본다(`docs/slices/3-이동/design.md` ②). 커밋까지 미루는 검사는 `SET CONSTRAINTS …
IMMEDIATE` 로 당겨 잰다 — 테스트 세션은 커밋하지 않고 되돌린다. 마지막 절은 두 연결로 동시에
넣는다."""

import math
import threading
import time
from collections.abc import Callable
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import TxnTypeAttribute
from app.db.inspection import Inspection
from app.db.inventory import Lot, StockLedgerEntry, StockTransferClosure, StockTransferRequest
from app.db.master import Item
from tests import test_purchase_returns as returns_case
from tests import test_retest as retest_case

# 로트는 2026-09-21 09:30 에 원재료창고로 500 이 들어왔고 2026-09-30 에
# 만료된다(`test_retest._plant`).
REQUESTED = datetime(2026, 9, 22, 9, 0)
PROCESSED = datetime(2026, 9, 22, 10, 0)
LOT_NUMBER = "RM-01-260921-01"

_TRANSFER_LINES = "stock_transfer_processing_has_its_ledger_lines"
_DISPOSAL_LINES = "retest_failure_has_its_disposal_line"


@pytest.fixture
def prepared(session: Session) -> Session:
    """원재료창고에 500 이 있는 원자재 로트 하나(입고 줄까지) — 만료일은 2026-09-30."""
    retest_case._plant(session)
    return session


def _the_lot(session: Session) -> Lot:
    return session.query(Lot).filter_by(lot_number=LOT_NUMBER).one()


def _add(session: Session, row: object) -> None:
    session.add(row)
    session.flush()


def _request(
    session: Session,
    lot: Lot,
    quantity: float = 200.0,
    requested_at: datetime = REQUESTED,
    **overrides: object,
) -> StockTransferRequest:
    """이동 요청 하나 — 제약을 통과하는 모양. 넘긴 값만 달라진다."""
    fields: dict[str, object] = {
        "lot_id": lot.id,
        "quantity": quantity,
        "requested_at": requested_at,
        "requested_by": "생산 1",
    }
    fields.update(overrides)
    request = StockTransferRequest(**fields)
    _add(session, request)
    return request


def _closure(
    request: StockTransferRequest,
    closure_type: str = codes.CLOSURE_PROCESSED,
    closed_at: datetime = PROCESSED,
    **overrides: object,
) -> StockTransferClosure:
    """그 요청의 종결 — 로트 · 수량 · 요청 시각을 요청에서 받는다. 넘긴 값만 달라진다."""
    fields: dict[str, object] = {
        "request_id": request.id,
        "closure_type": closure_type,
        "lot_id": request.lot_id,
        "quantity": request.quantity,
        "requested_at": request.requested_at,
        "closed_at": closed_at,
        "closed_by": "자재 담당 1",
    }
    fields.update(overrides)
    return StockTransferClosure(**fields)


def _line(
    session: Session, closure: StockTransferClosure, txn_type: str, **overrides: object
) -> StockLedgerEntry:
    """처리 종결이 내는 원장 줄 하나 — 유형이 정하는 창고에. 넘긴 값만 달라진다."""
    lot = session.get(Lot, closure.lot_id)
    assert lot is not None
    fields: dict[str, object] = {
        "lot_id": closure.lot_id,
        "inspection_id": lot.inspection_id,
        "txn_type": txn_type,
        "warehouse": codes.LEDGER_TYPE_WAREHOUSES[txn_type],
        "item_type": lot.item_type,
        "quantity": closure.quantity,
        "occurred_at": closure.closed_at,
        "transfer_closure_id": closure.id,
        "transfer_closure_type": closure.closure_type,
    }
    fields.update(overrides)
    return StockLedgerEntry(**fields)


def _process(
    session: Session,
    request: StockTransferRequest,
    closed_at: datetime = PROCESSED,
    *,
    sides: tuple[str, ...] = codes.TRANSFER_TXN_TYPES,
) -> StockTransferClosure:
    """처리 — 종결을 먼저, 넘긴 쪽의 원장 줄을 나중에. 쓰기 경로가 한 트랜잭션에서 할 일."""
    closure = _closure(request, closed_at=closed_at)
    _add(session, closure)
    for txn_type in sides:
        _add(session, _line(session, closure, txn_type))
    return closure


def _move(
    session: Session,
    lot: Lot,
    quantity: float,
    at: datetime = PROCESSED,
) -> StockTransferClosure:
    """요청하고 곧바로 처리한다."""
    return _process(session, _request(session, lot, quantity, requested_at=at), closed_at=at)


def _balance(session: Session, lot_id: int, warehouse: str) -> float:
    return float(
        session.execute(
            text(
                "SELECT coalesce(sum(CASE a.total_effect WHEN '증가' THEN e.quantity"
                " ELSE -e.quantity END), 0)"
                " FROM stock_ledger_entries AS e JOIN txn_type_attributes AS a"
                " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
                " WHERE e.lot_id = :lot AND e.warehouse = :warehouse"
            ),
            {"lot": lot_id, "warehouse": warehouse},
        ).scalar_one()
    )


def _immediately(session: Session, *constraints: str) -> None:
    """커밋까지 미뤄 두는 검사를 지금 돌린다 — 테스트 세션은 커밋하지 않고 되돌리므로."""
    session.execute(text(f"SET CONSTRAINTS {', '.join(constraints)} IMMEDIATE"))


# ── 요청 — 의도이지 사실이 아니다 ───────────────────────────────────────────


def test_a_request_holds_no_stock(prepared: Session) -> None:
    """**요청은 재고를 잡지 않는다** — 로트에 있는 것보다 많이 요청해도 선다. 잔량은 처리하는
    순간 원장이 본다."""
    _request(prepared, _the_lot(prepared), 900.0)


@pytest.mark.parametrize(
    "quantity", [0.0, -1.0, math.nan, math.inf], ids=["zero", "negative", "nan", "infinity"]
)
def test_a_request_moves_something(prepared: Session, quantity: float) -> None:
    """**0 은 요청이 아니다** — 그리고 하한 하나로는 `NaN` 과 무한대를 막지 못한다."""
    with pytest.raises(IntegrityError, match="ck_stock_transfer_request_quantity"):
        _request(prepared, _the_lot(prepared), quantity)


def test_a_request_names_who_asked(prepared: Session) -> None:
    """**요청자는 식별 칸이다** — 전각 공백은 비어 있다(`is_present()`)."""
    with pytest.raises(
        IntegrityError, match="ck_stock_transfer_request_requested_by_is_present"
    ):
        _request(prepared, _the_lot(prepared), requested_by="　")


def test_a_request_comes_after_the_lot_came_in(prepared: Session) -> None:
    """**들어오기 전의 물건은 옮기지 않는다** — 요청 시각이 그 로트의 입고 줄보다 앞서면 받지
    않는다. 원장 가드는 처리가 내는 줄만 보므로 요청 자체를 따로 본다."""
    with pytest.raises(IntegrityError, match="들어오기 전의 물건이다"):
        _request(prepared, _the_lot(prepared), requested_at=datetime(2026, 9, 21, 9, 0))


def test_a_lot_with_no_receipt_is_not_requested(prepared: Session) -> None:
    """**입고 줄이 없는 로트에는 요청이 서지 않는다** — 들어왔다는 사실이 없다."""
    material = prepared.query(Item).one()
    unreceived = retest_case._a_lot(
        prepared, material, "RM-01-260921-02", retest_case.EXPIRES, receipt=False
    )
    with pytest.raises(IntegrityError, match="입고 줄이 없다"):
        _request(prepared, unreceived)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE stock_transfer_requests SET quantity = 100",
        "UPDATE stock_transfer_requests SET requested_by = '생산 2'",
        "DELETE FROM stock_transfer_requests",
    ],
    ids=["quantity", "requester", "erase"],
)
def test_a_request_is_never_rewritten(prepared: Session, statement: str) -> None:
    """**잘못 낸 요청은 취소하고 새로 낸다**(원칙 ⑦) — 고치지도 지우지도 않는다."""
    _request(prepared, _the_lot(prepared))
    with pytest.raises(IntegrityError, match="이동 요청은 고치거나 지우지 않는다"):
        prepared.execute(text(statement))


# ── 종결 — 요청 하나에 처리 또는 취소 하나 (ADR 0023) ────────────────────────


@pytest.mark.parametrize(
    ("first", "then"),
    [
        (codes.CLOSURE_PROCESSED, codes.CLOSURE_CANCELLED),
        (codes.CLOSURE_CANCELLED, codes.CLOSURE_PROCESSED),
        (codes.CLOSURE_CANCELLED, codes.CLOSURE_CANCELLED),
    ],
    ids=["processed-then-cancelled", "cancelled-then-processed", "cancelled-twice"],
)
def test_one_request_has_one_end(prepared: Session, first: str, then: str) -> None:
    """**처리된 요청은 취소되지 않고 취소된 요청은 처리되지 않는다** — 트리거가 아니라 유일키
    하나가 지킨다(`PRD.md` 성공 기준 3)."""
    request = _request(prepared, _the_lot(prepared))
    if first == codes.CLOSURE_PROCESSED:
        _process(prepared, request)
    else:
        _add(prepared, _closure(request, first))

    with pytest.raises(IntegrityError, match="uq_stock_transfer_closure_request"):
        _add(prepared, _closure(request, then, closed_at=datetime(2026, 9, 22, 11, 0)))


def test_an_end_is_a_processing_or_a_cancellation(prepared: Session) -> None:
    """**구분은 둘뿐이다** — 다른 글자를 적은 종결이 유일키를 차지하면 요청이 처리도 취소도 아닌
    채로 끝난다."""
    request = _request(prepared, _the_lot(prepared))
    with pytest.raises(IntegrityError, match="ck_stock_transfer_closure_type"):
        _add(prepared, _closure(request, "보류"))


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": 100.0},
        {"requested_at": datetime(2026, 9, 22, 8, 0)},
        {"lot": "other"},
    ],
    ids=["part-of-it", "another-request-time", "another-lot"],
)
def test_an_end_carries_what_its_request_says(
    prepared: Session, change: dict[str, object]
) -> None:
    """**요청의 로트 · 수량 · 요청 시각을 쌍으로 받는다** — 처리 수량은 요청 수량과 같다(부분
    처리 없음, `PRD.md` 성공 기준 4). 모자라면 새 요청을 낸다."""
    request = _request(prepared, _the_lot(prepared))
    overrides = dict(change)
    if overrides.pop("lot", None) == "other":
        material = prepared.query(Item).one()
        other = retest_case._a_lot(prepared, material, "RM-01-260921-02", retest_case.EXPIRES)
        overrides["lot_id"] = other.id

    with pytest.raises(IntegrityError, match="fk_stock_transfer_closure_request"):
        _add(prepared, _closure(request, codes.CLOSURE_CANCELLED, **overrides))


def test_an_end_does_not_come_before_its_request(prepared: Session) -> None:
    """**요청보다 먼저 끝나지 않는다** — 받은 요청 시각을 한 줄 안의 CHECK 가 견준다."""
    request = _request(prepared, _the_lot(prepared))
    with pytest.raises(IntegrityError, match="ck_stock_transfer_closure_after_the_request"):
        _add(
            prepared,
            _closure(request, codes.CLOSURE_CANCELLED, closed_at=datetime(2026, 9, 22, 8, 59)),
        )


def test_an_end_names_who_closed_it(prepared: Session) -> None:
    request = _request(prepared, _the_lot(prepared))
    with pytest.raises(IntegrityError, match="ck_stock_transfer_closure_closed_by_is_present"):
        _add(prepared, _closure(request, codes.CLOSURE_CANCELLED, closed_by="\t"))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE stock_transfer_closures SET closed_by = '자재 담당 2'",
        "UPDATE stock_transfer_closures SET closure_type = '처리'",
        "DELETE FROM stock_transfer_closures",
    ],
    ids=["closer", "type", "erase"],
)
def test_an_end_is_never_rewritten(prepared: Session, statement: str) -> None:
    """**종결은 일어난 일이다** — 취소를 처리로 고치거나 지우면 거두어진 요청이 되살아난다."""
    request = _request(prepared, _the_lot(prepared))
    _add(prepared, _closure(request, codes.CLOSURE_CANCELLED))
    with pytest.raises(IntegrityError, match="이동 종결은 고치거나 지우지 않는다"):
        prepared.execute(text(statement))


def test_anyone_may_cancel_and_a_cancellation_moves_nothing(prepared: Session) -> None:
    """**취소는 누구든 낸다** — 취소자를 요청자와 견주지 않는다(소유자, 2026-10-19). 취소는
    처리되기 전의 의도를 거두는 것이라 원장 줄이 없고, 커밋 때의 검사도 줄을 요구하지 않는다."""
    lot = _the_lot(prepared)
    request = _request(prepared, lot)
    _add(prepared, _closure(request, codes.CLOSURE_CANCELLED, closed_by="다른 사람"))

    _immediately(prepared, _TRANSFER_LINES)
    assert _balance(prepared, lot.id, codes.WAREHOUSE_RAW) == 500.0
    assert _balance(prepared, lot.id, codes.WAREHOUSE_PRODUCTION) == 0.0


# ── 처리 — 종결 · 생산출고 · 생산입고가 한 트랜잭션 ─────────────────────────


def test_processing_moves_the_lot_across_warehouses(prepared: Session) -> None:
    """**같은 로트가 두 창고에 나뉜다**(`PRD.md` 시나리오 ①) — 로트 번호는 그대로이고, 세 줄이
    같은 로트 · 같은 수량 · 같은 시각을 가리킨다(성공 기준 2)."""
    lot = _the_lot(prepared)
    _move(prepared, lot, 200.0)

    _immediately(prepared, _TRANSFER_LINES)
    assert _balance(prepared, lot.id, codes.WAREHOUSE_RAW) == 300.0
    assert _balance(prepared, lot.id, codes.WAREHOUSE_PRODUCTION) == 200.0


@pytest.mark.parametrize(
    "sides",
    [(), (codes.TXN_TRANSFER_OUT,), (codes.TXN_TRANSFER_IN,)],
    ids=["no-line", "only-out", "only-in"],
)
def test_processing_takes_both_ledger_lines(prepared: Session, sides: tuple[str, ...]) -> None:
    """**처리와 두 줄은 함께 선다** — 처리가 홀로 서면 재고가 원재료창고에 그대로 남고, 한쪽만
    서면 물건이 한 창고에서 사라지거나 생산창고에서 생긴다. 커밋할 때 묻는다."""
    _process(prepared, _request(prepared, _the_lot(prepared)), sides=sides)

    with pytest.raises(IntegrityError, match="두 줄이 다 서지 않았다"):
        _immediately(prepared, _TRANSFER_LINES)


def test_a_transfer_line_names_its_processing(prepared: Session) -> None:
    """**양방향이다** — 이동 줄이 종결을 비우면 가리키는 외래키가 통째로 건너뛰어진다."""
    closure = _process(prepared, _request(prepared, _the_lot(prepared)), sides=())
    with pytest.raises(
        IntegrityError, match="ck_stock_ledger_entry_transfer_names_its_closure"
    ):
        _add(
            prepared,
            _line(
                prepared,
                closure,
                codes.TXN_TRANSFER_OUT,
                transfer_closure_id=None,
                transfer_closure_type=None,
            ),
        )


def test_only_a_transfer_line_names_a_processing(prepared: Session) -> None:
    """**양방향의 다른 쪽** — 이동이 아닌 줄이 종결을 들면 다른 줄이 이동의 근거를 들고 있다."""
    lot = _the_lot(prepared)
    closure = _process(prepared, _request(prepared, lot), sides=())
    retest = retest_case._retest(prepared, codes.JUDGMENT_FAILED)
    _add(prepared, retest)
    with pytest.raises(
        IntegrityError, match="ck_stock_ledger_entry_transfer_names_its_closure"
    ):
        _add(
            prepared,
            retest_case._disposal(
                prepared,
                retest,
                transfer_closure_id=closure.id,
                transfer_closure_type=closure.closure_type,
            ),
        )


@pytest.mark.parametrize(
    "closure_type", [None, codes.CLOSURE_CANCELLED], ids=["empty", "cancel"]
)
def test_a_transfer_line_follows_a_processing(
    prepared: Session, closure_type: str | None
) -> None:
    """**구분은 종결과 함께 차고, 차면 처리다** — 비면 외래키가 건너뛰어지고, 「취소」를 적고
    취소 종결을 가리키면 외래키는 짝을 찾아 지나간다. 거두어진 요청으로 재고가 옮겨 간다."""
    request = _request(prepared, _the_lot(prepared))
    cancelled = _closure(request, codes.CLOSURE_CANCELLED)
    _add(prepared, cancelled)
    with pytest.raises(
        IntegrityError, match="ck_stock_ledger_entry_transfer_follows_a_processing"
    ):
        _add(
            prepared,
            _line(
                prepared, cancelled, codes.TXN_TRANSFER_OUT, transfer_closure_type=closure_type
            ),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": 50.0},
        {"occurred_at": datetime(2026, 9, 22, 11, 0)},
        {"lot": "other"},
    ],
    ids=["another-quantity", "another-time", "another-lot"],
)
def test_a_transfer_line_says_what_its_processing_says(
    prepared: Session, change: dict[str, object]
) -> None:
    """**같은 로트 · 같은 수량 · 같은 시각까지 가리킨다**(`PRD.md` 성공 기준 2) — 종결만
    가리키면 요청은 200 을 옮겼는데 원장은 50 을 옮기는 줄이 선다."""
    closure = _process(prepared, _request(prepared, _the_lot(prepared)), sides=())
    overrides = dict(change)
    if overrides.pop("lot", None) == "other":
        material = prepared.query(Item).one()
        other = retest_case._a_lot(prepared, material, "RM-01-260921-02", retest_case.EXPIRES)
        overrides.update(lot_id=other.id, inspection_id=other.inspection_id)

    with pytest.raises(IntegrityError, match="fk_stock_ledger_entry_transfer_closure"):
        _add(prepared, _line(prepared, closure, codes.TXN_TRANSFER_OUT, **overrides))


def test_one_processing_takes_one_line_on_each_side(prepared: Session) -> None:
    """**처리 하나에 출고 줄 하나** — 둘째 출고 줄은 잔량이 남아 있어도 받지 않는다. 한 번 옮긴
    것을 두 번 뺀다."""
    closure = _process(prepared, _request(prepared, _the_lot(prepared)))
    with pytest.raises(
        IntegrityError, match="uq_stock_ledger_entry_one_line_per_transfer_side"
    ):
        _add(prepared, _line(prepared, closure, codes.TXN_TRANSFER_OUT))


@pytest.mark.parametrize(
    ("txn_type", "warehouse"),
    [
        (codes.TXN_TRANSFER_OUT, codes.WAREHOUSE_PRODUCTION),
        (codes.TXN_TRANSFER_IN, codes.WAREHOUSE_RAW),
    ],
    ids=["out-of-production", "into-raw"],
)
def test_a_transfer_runs_from_raw_to_production(
    prepared: Session, txn_type: str, warehouse: str
) -> None:
    """**출고는 원재료창고 · 입고는 생산창고다**(`PRD.md` 성공 기준 2) — 유형이 창고를 정한다.
    잔량 트리거는 설 수 없는 창고의 줄을 넘겨 CHECK 가 그 이름으로 말하게 한다."""
    closure = _process(prepared, _request(prepared, _the_lot(prepared)), sides=())
    with pytest.raises(IntegrityError, match="ck_stock_ledger_entry_type_sets_warehouse"):
        _add(prepared, _line(prepared, closure, txn_type, warehouse=warehouse))


# ── 잔량 — 로트 × 창고 (ADR 0013) ───────────────────────────────────────────


def test_a_transfer_takes_no_more_than_the_raw_warehouse_holds(prepared: Session) -> None:
    """**생산창고가 원재료창고에 빌려주지 않는다**(`PRD.md` 성공 기준 1) — 로트에는 500 이
    있지만 원재료창고에는 200 뿐이다. 로트 하나로 세면 생산창고의 300 을 빌려 지나간다."""
    lot = _the_lot(prepared)
    _move(prepared, lot, 300.0)

    with pytest.raises(IntegrityError, match="원재료 창고 잔량이 -100"):
        _move(prepared, lot, 300.0, at=datetime(2026, 9, 23, 10, 0))


def test_a_transfer_line_does_not_come_before_the_lot_came_in(prepared: Session) -> None:
    """**나가는 줄의 시각은 입고 줄과 견준다** — 요청의 시각 검사와 별도로, 처리가 낸 줄도 잔량
    트리거의 같은 견줌을 받는다."""
    closure = _process(prepared, _request(prepared, _the_lot(prepared)), sides=())
    early = datetime(2026, 9, 21, 9, 0)
    with pytest.raises(IntegrityError, match="들어오기 전의 물건이다"):
        _add(prepared, _line(prepared, closure, codes.TXN_TRANSFER_OUT, occurred_at=early))


def test_what_moved_to_production_is_not_returned(session: Session) -> None:
    """**구매반품은 원재료창고의 잔량을 넘지 못한다**(`PRD.md` 「착공에서 답을 받은 것」) —
    생산창고로 옮긴 분량은 공급사에 돌려보내지 않는다. 반품 줄은 원재료창고에만 서고 잔량을
    창고마다 세므로 반품 문서의 트리거를 따로 고치지 않아도 막힌다."""
    returns_case._plant(session)
    # 반품 쪽 바탕은 이동 유형의 속성을 심지 않는다 — 그 방향만 더한다.
    session.add_all(
        TxnTypeAttribute(
            code=txn_type,
            total_effect=codes.LEDGER_EFFECTS[txn_type],
            source_document_type="시험",
        )
        for txn_type in codes.TRANSFER_TXN_TYPES
    )
    session.flush()
    lot = returns_case._the_lot(session)
    _move(session, lot, 300.0)

    document = returns_case._lot_return(session, 300.0)
    _add(session, document)
    with pytest.raises(IntegrityError, match="원재료 창고 잔량이 -100"):
        _add(session, returns_case._return_line(document))


# ── 나뉜 로트의 폐기 — 잔량이 남은 창고마다 한 줄 ───────────────────────────


def _split_and_fail(session: Session) -> tuple[Lot, Inspection]:
    """원재료창고 300 · 생산창고 200 으로 나눈 뒤 재검사에서 떨어뜨린다 — 폐기 줄은 아직
    없다."""
    lot = _the_lot(session)
    _move(session, lot, 200.0, at=datetime(2026, 9, 25, 10, 0))
    retest = retest_case._retest(session, codes.JUDGMENT_FAILED)
    _add(session, retest)
    return lot, retest


def _disposal(
    session: Session, retest: Inspection, warehouse: str, quantity: float
) -> StockLedgerEntry:
    return retest_case._disposal(session, retest, quantity, warehouse=warehouse)


def test_a_split_lot_is_disposed_of_in_each_warehouse(prepared: Session) -> None:
    """**잔량이 남은 창고마다 폐기 줄 하나, 합쳐서 잔량 전부**(`PRD.md` 시나리오 ③ · 성공 기준
    6)."""
    lot, retest = _split_and_fail(prepared)
    _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_RAW, 300.0))
    _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_PRODUCTION, 200.0))

    _immediately(prepared, _DISPOSAL_LINES, _TRANSFER_LINES)
    assert _balance(prepared, lot.id, codes.WAREHOUSE_RAW) == 0.0
    assert _balance(prepared, lot.id, codes.WAREHOUSE_PRODUCTION) == 0.0


def test_a_disposal_that_misses_a_warehouse_does_not_stand(prepared: Session) -> None:
    """**창고 하나를 빠뜨린 폐기는 서지 않는다** — 줄 하나하나는 그 창고의 잔량 전부라 줄마다의
    검사를 지난다. 「모든 창고가 비었는가」는 커밋할 때 묻는다."""
    _, retest = _split_and_fail(prepared)
    _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_RAW, 300.0))

    with pytest.raises(IntegrityError, match="200이 남는다 — 잔량이 남은 창고마다"):
        _immediately(prepared, _DISPOSAL_LINES)


def test_a_disposal_takes_its_whole_warehouse(prepared: Session) -> None:
    """**폐기 줄은 그 창고의 잔량 전부다** — 일부만 버리면 떨어진 물건이 그 창고에 남는다."""
    _, retest = _split_and_fail(prepared)
    with pytest.raises(IntegrityError, match="생산 창고 잔량 전부다 — 100이 남는다"):
        _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_PRODUCTION, 100.0))


def test_a_disposal_does_not_take_from_a_warehouse_the_lot_never_reached(
    prepared: Session,
) -> None:
    """**들어온 적 없는 창고에서 버리지 못한다** — 잔량을 로트 하나로 세던 때는 지나갔다(그래서
    리비전의 가드가 그런 옛 줄을 묻는다)."""
    retest = retest_case._retest(prepared, codes.JUDGMENT_FAILED)
    _add(prepared, retest)
    with pytest.raises(IntegrityError, match="생산 창고 잔량이 -500"):
        _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_PRODUCTION, 500.0))


def test_one_retest_takes_one_disposal_line_in_each_warehouse(prepared: Session) -> None:
    """**재검사 하나에 폐기 줄은 창고마다 하나다** — 늦게 적은 이동이 폐기 뒤에 그 창고를 다시
    채우면 둘째 폐기 줄이 잔량 규칙을 지난다. 그러면 같은 창고에서 두 번 버린 재검사가 커밋 때의
    검사까지 지난다."""
    lot, retest = _split_and_fail(prepared)
    _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_PRODUCTION, 200.0))
    # 2026-09-26 의 이동을 늦게 적는다 — 그 시각에는 로트가 살아 있었다.
    _move(prepared, lot, 100.0, at=datetime(2026, 9, 26, 10, 0))

    with pytest.raises(
        IntegrityError, match="uq_stock_ledger_entry_one_line_per_retest_warehouse"
    ):
        _add(prepared, _disposal(prepared, retest, codes.WAREHOUSE_PRODUCTION, 100.0))


# ── 만료된 로트의 처리를 막는다 — 처리 시각에 살아 있던 만료일로 ──────────────


def _process_at(session: Session, at: datetime, lot: Lot | None = None) -> None:
    request = _request(
        session, lot or _the_lot(session), requested_at=datetime(2026, 9, 22, 9, 0)
    )
    _process(session, request, closed_at=at)


def test_an_expired_lot_is_not_moved(prepared: Session) -> None:
    """**만료일 다음 날부터는 옮기지 않는다**(`PRD.md` 성공 기준 5)."""
    with pytest.raises(IntegrityError, match="만료된 로트는 옮기지 않는다"):
        _process_at(prepared, datetime(2026, 10, 1, 0, 0))


def test_a_lot_still_moves_on_its_expiry_day(prepared: Session) -> None:
    """**만료일 당일까지는 쓸 수 있다** — 재검사와 같은 경계다."""
    _process_at(prepared, datetime(2026, 9, 30, 23, 59))


def test_a_request_for_an_expired_lot_still_stands_and_can_be_cancelled(
    prepared: Session,
) -> None:
    """**요청은 막지 않는다** — 요청은 의도이고 만료는 옮기는 순간의 사실이다. 거두는 것도 막지
    않는다."""
    request = _request(prepared, _the_lot(prepared), requested_at=datetime(2026, 10, 5, 9, 0))
    _add(
        prepared,
        _closure(request, codes.CLOSURE_CANCELLED, closed_at=datetime(2026, 10, 5, 10, 0)),
    )


def test_a_renewal_judged_after_the_processing_does_not_cover_it(prepared: Session) -> None:
    """**처리 시각에 살아 있던 만료일로 견준다** — 뒤에 선 갱신 재검사를 믿으면 그보다 이른
    처리를 받아, 원장이 만료된 로트를 옮겼다고 말한다(PR #96 Codex 리뷰)."""
    _add(prepared, retest_case._retest(prepared))  # 2026-10-02 합격, 2027-10-02 까지

    with pytest.raises(IntegrityError, match="만료된 로트는 옮기지 않는다"):
        _process_at(prepared, datetime(2026, 10, 1, 12, 0))


def test_a_renewed_lot_moves_again(prepared: Session) -> None:
    """**갱신된 만료일은 그 재검사부터 산다.**"""
    _add(prepared, retest_case._retest(prepared))

    _process_at(prepared, datetime(2026, 10, 3, 9, 0))


def test_a_lot_without_an_expiry_moves_any_day(prepared: Session) -> None:
    """**만료일이 없으면 만료가 아니다.**"""
    material = prepared.query(Item).one()
    forever = retest_case._a_lot(prepared, material, "RM-01-260921-02", None)

    _process_at(prepared, datetime(2030, 1, 1, 9, 0), lot=forever)


@pytest.mark.parametrize(
    "at",
    [datetime(2026, 9, 30, 23, 59), datetime(2026, 10, 1, 0, 0), datetime(2026, 10, 1, 23, 59)],
    ids=["expiry-day", "next-day-start", "next-day-end"],
)
def test_processing_and_retest_share_one_boundary(prepared: Session, at: datetime) -> None:
    """**경계는 재검사와 같다**(`docs/schema-4단계.md` 「새 트리거」) — 같은 시각에 재검사를
    받을 수 있으면 처리는 막히고, 처리가 되면 재검사는 막힌다. 둘이 갈리면 재검사를 받을 수도
    옮길 수도 없는 날이나, 둘 다 되는 날이 생긴다."""

    def accepted(write: Callable[[], None]) -> bool:
        savepoint = prepared.begin_nested()
        try:
            write()
        except IntegrityError:
            savepoint.rollback()
            return False
        savepoint.rollback()
        return True

    retest_taken = accepted(lambda: _add(prepared, retest_case._retest(prepared, judged_at=at)))
    moved = accepted(lambda: _process_at(prepared, at))

    assert retest_taken != moved, (at, retest_taken, moved)


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


def _race(
    scoped: Engine,
    first_write: Callable[[Session], None],
    second_write: Callable[[Session], None],
) -> object:
    """**첫째가 잡은 채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를 커밋한다.**
    기다리는지를 보지 않고 커밋하면 둘째가 첫째의 커밋 뒤에 출발했을 때 잠금이 없어도 통과한다 —
    `tests/test_retest.py` 의 같은 이름 함수와 같은 자리다."""
    first = Session(scoped)
    second = Session(scoped)
    outcome: dict[str, object] = {}
    try:
        first_write(first)
        pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def go() -> None:
            try:
                second_write(second)
                second.commit()
                outcome["second"] = "committed"
            except IntegrityError as error:
                second.rollback()
                outcome["second"] = error

        racer = threading.Thread(target=go)
        racer.start()
        deadline = time.monotonic() + 10
        with scoped.connect() as watcher:
            while racer.is_alive() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                ).scalar_one_or_none()
                if waiting == "Lock":
                    break
                time.sleep(0.02)
        assert racer.is_alive(), "둘째가 기다리지 않고 끝났다 — 이 시험이 잠금을 재지 못한다"
        first.commit()
        racer.join(10)
        assert not racer.is_alive(), "둘째가 끝나지 않았다"
    finally:
        first.close()
        second.close()
    return outcome["second"]


def _requests_of(session: Session, *quantities: float) -> list[int]:
    lot = _the_lot(session)
    ids = [_request(session, lot, quantity).id for quantity in quantities]
    session.commit()
    return ids


def test_two_processings_of_one_lot_at_once_do_not_both_take_it(engine: Engine) -> None:
    """**같은 로트의 두 처리가 동시에 와도 막힌다**(`PRD.md` 성공 기준 1) — 원재료창고 500 에서
    300 씩. 잠그지 않으면 둘 다 500 을 보고 지나가 원재료창고가 −100 이 된다."""
    with retest_case._committed_schema(engine, "transfer_race_two_processings") as scoped:
        with Session(scoped) as setup:
            first_id, second_id = _requests_of(setup, 300.0, 300.0)

        def process(request_id: int) -> Callable[[Session], None]:
            def write(session: Session) -> None:
                request = session.get(StockTransferRequest, request_id)
                assert request is not None
                _process(session, request)

            return write

        second = _race(scoped, process(first_id), process(second_id))

        assert isinstance(second, IntegrityError), second
        assert "원재료 창고 잔량이 -100" in str(second)


def test_processing_and_cancelling_one_request_at_once(engine: Engine) -> None:
    """**같은 요청의 처리와 취소가 동시에 오면 유일키에서 하나가 진다**(ADR 0023) — 트리거로
    「이미 끝났는가」를 묻는 모양이었다면 둘 다 「아직」을 보고 함께 섰다."""
    with retest_case._committed_schema(engine, "transfer_race_process_cancel") as scoped:
        with Session(scoped) as setup:
            (request_id,) = _requests_of(setup, 200.0)

        def process(session: Session) -> None:
            request = session.get(StockTransferRequest, request_id)
            assert request is not None
            _process(session, request)

        def cancel(session: Session) -> None:
            request = session.get(StockTransferRequest, request_id)
            assert request is not None
            _add(session, _closure(request, codes.CLOSURE_CANCELLED))

        second = _race(scoped, process, cancel)

        assert isinstance(second, IntegrityError), second
        assert "uq_stock_transfer_closure_request" in str(second)


def test_a_retest_waits_for_a_processing_of_the_same_lot(engine: Engine) -> None:
    """**재검사와 처리는 로트 줄에서 줄을 선다** — 처리가 커밋되기를 기다린 재검사는 나뉜 로트를
    본다. 들어온 창고에 로트 전체(500)를 버리는 폐기 줄은 그 창고의 300 을 넘어 거부된다. 줄을
    서지 않으면 처리가 커밋되기 전의 잔량(원재료창고 500)을 보고 지나가, 처리와 폐기가 함께
    원재료창고를 음수로 만든다."""
    with retest_case._committed_schema(engine, "transfer_race_retest") as scoped:
        with Session(scoped) as setup:
            (request_id,) = _requests_of(setup, 200.0)

        def process(session: Session) -> None:
            request = session.get(StockTransferRequest, request_id)
            assert request is not None
            _process(session, request, closed_at=datetime(2026, 9, 25, 10, 0))

        def fail_and_dispose_where_it_came_in(session: Session) -> None:
            retest = retest_case._retest(session, codes.JUDGMENT_FAILED)
            _add(session, retest)
            _add(session, _disposal(session, retest, codes.WAREHOUSE_RAW, 500.0))

        second = _race(scoped, process, fail_and_dispose_where_it_came_in)

        assert isinstance(second, IntegrityError), second
        assert "원재료 창고 잔량이 -200" in str(second), second
