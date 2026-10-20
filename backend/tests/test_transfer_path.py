"""재고이동 쓰기 경로 — 4단계 조각 3(이동) PR C. **요청 → 처리 또는 취소.**

PR A 가 표와 트리거를 세웠고, 이 PR 은 그것을 **한 트랜잭션으로 부르는 자리**다. 여기서 보는
것은 —

- **처리는 종결과 원장 두 줄이 함께 서는가**, 취소는 원장을 건드리지 않는가
- **트리거 · 유일키가 막는 것을 쓰기 경로가 먼저 이름으로 막는가** — 그리고 **같은 경계로**
  막는가(만료 · 원재료창고의 잔량)
- **반품이 원재료창고의 잔량을 넘지 못하는가** — 생산창고로 옮긴 분량은 돌려보내지 않는다
- **동시에 와도 둘째가 이름을 받는가** — 같은 로트의 두 처리, 같은 요청의 처리와 취소

트리거 자체는 `tests/test_stock_transfer.py` 가 본다.
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.api.schemas import LotRefusal
from app.core import clock, codes
from app.db.base import Base
from app.db.inventory import Lot, StockLedgerEntry, StockTransferClosure, StockTransferRequest
from app.services.retests import RetestRefusal, retest
from app.services.returns import RefusedReturn, ReturnRefusal, return_to_supplier
from app.services.site_clock import assert_the_site_clock_holds, latest_stamp
from app.services.transfers import (
    IncomingTransferClosure,
    IncomingTransferRequest,
    RefusedTransfer,
    TransferClosed,
    TransferClosureRefusal,
    TransferRequestRefusal,
    close_transfer,
    request_transfer,
)
from tests.test_retest_path import (
    a_retest,
    an_expired_lot,
    plant_retest_data,
    plant_transfer_types,
)
from tests.test_return_path import _from_the_lot

_RAW, _PRODUCTION = codes.WAREHOUSE_RAW, codes.WAREHOUSE_PRODUCTION


def plant_transfer_data(session: Session) -> None:
    """재검사의 기준정보(관문 1 · 반품 포함) 위에 이동의 유형과 생산창고."""
    plant_retest_data(session)
    plant_transfer_types(session)


@pytest.fixture
def planted(session: Session) -> Session:
    plant_transfer_data(session)
    return session


def a_live_lot(
    session: Session, *, quantity: float = 500.0, expires_in: int | None = 30
) -> Lot:
    """살아 있는 로트 — 400 일 전에 들어왔고 만료일이 `expires_in` 일 뒤다(`None` 이면 만료일이
    없다). 원재료창고에 `quantity`."""
    return an_expired_lot(
        session,
        quantity=quantity,
        expires=None if expires_in is None else clock.today() + timedelta(days=expires_in),
        no_expiry=expires_in is None,
    )


def _ask(session: Session, lot_id: int, quantity: float, by: str = "생산 1") -> int:
    return request_transfer(
        session, IncomingTransferRequest(lot_id=lot_id, quantity=quantity, requested_by=by)
    ).transfer_request_id


def _close(
    session: Session, request_id: int, closure_type: str, by: str = "자재 담당 1"
) -> TransferClosed:
    return close_transfer(
        session,
        IncomingTransferClosure(
            transfer_request_id=request_id, closure_type=closure_type, closed_by=by
        ),
    )


def _process(session: Session, request_id: int) -> TransferClosed:
    return _close(session, request_id, codes.CLOSURE_PROCESSED)


def _cancel(session: Session, request_id: int, by: str = "자재 담당 1") -> TransferClosed:
    return _close(session, request_id, codes.CLOSURE_CANCELLED, by)


def _refused(write: Callable[[], object]) -> str:
    with pytest.raises(RefusedTransfer) as refused:
        write()
    return refused.value.code


def _balances(session: Session, lot_id: int) -> dict[str, float]:
    """로트의 창고별 원장 합 — 트리거와 같은 셈이다."""
    rows = session.execute(
        text(
            "SELECT e.warehouse, sum(CASE a.total_effect WHEN :up THEN e.quantity::numeric"
            " ELSE -e.quantity::numeric END)"
            " FROM stock_ledger_entries AS e JOIN txn_type_attributes AS a"
            " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
            " WHERE e.lot_id = :lot GROUP BY e.warehouse"
        ),
        {"up": codes.EFFECT_INCREASE, "lot": lot_id},
    ).all()
    return {warehouse: float(total) for warehouse, total in rows}


def _lines_of(session: Session, closure_id: int) -> int:
    counted = session.scalar(
        select(func.count())
        .select_from(StockLedgerEntry)
        .where(StockLedgerEntry.transfer_closure_id == closure_id)
    )
    return int(counted or 0)


# ── 두 갈래 — 처리 · 취소 ──────────────────────────────────────────────────


def test_processing_moves_the_quantity_in_one_transaction(planted: Session) -> None:
    """**종결 · 생산출고 · 생산입고가 함께 선다** — 같은 로트 · 같은 수량 · 같은 시각으로.
    출고는 원재료창고, 입고는 생산창고다. 응답의 id 는 출고 · 입고 순서다."""
    lot = a_live_lot(planted)
    request_id = _ask(planted, lot.id, 200.0)

    closed = _process(planted, request_id)

    closure = planted.scalars(
        select(StockTransferClosure).where(StockTransferClosure.request_id == request_id)
    ).one()
    lines = [planted.get(StockLedgerEntry, entry_id) for entry_id in closed.ledger_entry_ids]
    assert [
        (
            line.txn_type,
            line.warehouse,
            line.quantity,
            line.occurred_at,
            line.transfer_closure_id,
        )
        for line in lines
        if line is not None
    ] == [
        (codes.TXN_TRANSFER_OUT, _RAW, 200.0, closure.closed_at, closure.id),
        (codes.TXN_TRANSFER_IN, _PRODUCTION, 200.0, closure.closed_at, closure.id),
    ]
    assert (closure.closure_type, closure.closed_by) == (codes.CLOSURE_PROCESSED, "자재 담당 1")
    assert _balances(planted, lot.id) == {_RAW: 300.0, _PRODUCTION: 200.0}


def test_a_request_holds_nothing_and_is_written_on_the_site_clock(
    planted: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**요청은 의도다** — 원장에 아무것도 남기지 않는다. 요청 시각과 처리 시각은 현장의
    벽시계다(ADR 0019) — UTC 와 14 시간 떨어진 곳이라 컨테이너 시각을 쓰면 드러난다."""
    monkeypatch.setenv("ERP_SITE_TIMEZONE", "Etc/GMT-14")
    lot = a_live_lot(planted)
    request_id = _ask(planted, lot.id, 200.0)
    request = planted.get(StockTransferRequest, request_id)
    assert request is not None

    assert (request.lot_id, request.quantity, request.requested_by) == (lot.id, 200.0, "생산 1")
    assert abs(clock.now() - request.requested_at) < timedelta(minutes=1)
    assert _balances(planted, lot.id) == {_RAW: 500.0}

    _process(planted, request_id)
    closure = planted.scalars(
        select(StockTransferClosure).where(StockTransferClosure.request_id == request_id)
    ).one()
    assert abs(clock.now() - closure.closed_at) < timedelta(minutes=1)


def test_cancelling_leaves_the_ledger_alone(planted: Session) -> None:
    """**취소는 새 사실이다** — 요청 줄은 그대로이고 원장 줄은 서지 않는다. **취소자는 누구든
    된다** — 요청자와 다른 사람의 취소도 받고, 그 이름이 남는다."""
    lot = a_live_lot(planted)
    request_id = _ask(planted, lot.id, 200.0, by="생산 1")

    closed = _cancel(planted, request_id, by="생산 2")

    assert closed == TransferClosed(())
    closure = planted.scalars(
        select(StockTransferClosure).where(StockTransferClosure.request_id == request_id)
    ).one()
    assert (closure.closure_type, closure.closed_by) == (codes.CLOSURE_CANCELLED, "생산 2")
    assert _lines_of(planted, closure.id) == 0
    assert planted.get(StockTransferRequest, request_id) is not None
    assert _balances(planted, lot.id) == {_RAW: 500.0}


def test_a_request_for_more_than_there_is_still_stands(planted: Session) -> None:
    """**요청은 재고를 잡지 않는다** — 잔량은 처리하는 순간에 본다. 처리는 이름으로 막히고,
    그 요청은 취소로 끝낼 수 있다."""
    lot = a_live_lot(planted)
    request_id = _ask(planted, lot.id, 800.0)

    assert _refused(lambda: _process(planted, request_id)) == (
        TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS
    )
    assert _cancel(planted, request_id) == TransferClosed(())


def test_a_lot_can_be_moved_out_whole(planted: Session) -> None:
    """**원재료창고의 잔량 전부까지 옮긴다** — 경계는 「넘으면」이다."""
    lot = a_live_lot(planted)
    _process(planted, _ask(planted, lot.id, 500.0))
    assert _balances(planted, lot.id) == {_RAW: 0.0, _PRODUCTION: 500.0}


def test_a_second_processing_counts_only_what_is_left_in_the_raw_warehouse(
    planted: Session,
) -> None:
    """**잔량은 로트 × 창고로 센다** — 로트 전체에 500 이 있어도 원재료창고에 300 이면 350 은
    옮기지 못한다. 생산창고의 200 을 빌리지 않는다."""
    lot = a_live_lot(planted)
    _process(planted, _ask(planted, lot.id, 200.0))
    request_id = _ask(planted, lot.id, 350.0)

    assert _refused(lambda: _process(planted, request_id)) == (
        TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS
    )
    _process(planted, _ask(planted, lot.id, 300.0))
    assert _balances(planted, lot.id) == {_RAW: 0.0, _PRODUCTION: 500.0}


def test_quantities_that_do_not_add_up_in_binary_still_empty_the_warehouse(
    planted: Session,
) -> None:
    """**트리거가 세는 자릿수로 센다** — `double precision` 으로 빼면 100 − 64.4 − 35.6 이 0 이
    아니라 음수가 되어, 트리거가 받는 처리를 이 경로가 거절한다."""
    lot = a_live_lot(planted, quantity=100.0)
    _process(planted, _ask(planted, lot.id, 64.4))
    _process(planted, _ask(planted, lot.id, 35.6))
    assert _balances(planted, lot.id) == {_RAW: 0.0, _PRODUCTION: 100.0}


# ── 이름 있는 거절 ─────────────────────────────────────────────────────────


def test_an_unknown_lot_is_named(planted: Session) -> None:
    assert _refused(lambda: _ask(planted, 2_000_000, 1.0)) == TransferRequestRefusal.UNKNOWN_LOT


def test_an_unknown_request_is_named(planted: Session) -> None:
    assert _refused(lambda: _process(planted, 2_000_000)) == (
        TransferClosureRefusal.UNKNOWN_TRANSFER_REQUEST
    )


@pytest.mark.parametrize(
    ("first", "then", "expected"),
    [
        (
            codes.CLOSURE_PROCESSED,
            codes.CLOSURE_CANCELLED,
            TransferClosureRefusal.REQUEST_IS_ALREADY_PROCESSED,
        ),
        (
            codes.CLOSURE_PROCESSED,
            codes.CLOSURE_PROCESSED,
            TransferClosureRefusal.REQUEST_IS_ALREADY_PROCESSED,
        ),
        (
            codes.CLOSURE_CANCELLED,
            codes.CLOSURE_PROCESSED,
            TransferClosureRefusal.REQUEST_IS_ALREADY_CANCELLED,
        ),
        (
            codes.CLOSURE_CANCELLED,
            codes.CLOSURE_CANCELLED,
            TransferClosureRefusal.REQUEST_IS_ALREADY_CANCELLED,
        ),
    ],
    ids=["cancel-processed", "process-twice", "process-cancelled", "cancel-twice"],
)
def test_a_request_closes_once(
    planted: Session, first: str, then: str, expected: TransferClosureRefusal
) -> None:
    """**요청 하나에 종결 하나**(ADR 0023) — 유일키가 지키는 것을 이름으로 먼저 말한다. 처리된
    요청이면 원장에 줄이 더 서지 않는다."""
    lot = a_live_lot(planted, quantity=1000.0)
    request_id = _ask(planted, lot.id, 200.0)
    _close(planted, request_id, first)
    before = _balances(planted, lot.id)

    assert _refused(lambda: _close(planted, request_id, then)) == expected
    assert _balances(planted, lot.id) == before


def test_an_expired_lot_is_requested_but_not_moved(planted: Session) -> None:
    """**요청은 막지 않고 처리만 막는다**(`PRD.md` 성공 기준 5) — 만료는 옮기는 순간의
    사실이다. 그 요청은 취소로 끝낼 수 있다."""
    lot = an_expired_lot(planted)
    request_id = _ask(planted, lot.id, 100.0)

    assert _refused(lambda: _process(planted, request_id)) == (
        TransferClosureRefusal.LOT_HAS_EXPIRED
    )
    assert _cancel(planted, request_id) == TransferClosed(())


def test_a_lot_renewed_by_a_retest_moves_again(planted: Session) -> None:
    """**살아 있는 만료일은 가장 늦게 합격한 재검사의 것이다** — 라벨의 만료일이 지났어도
    재검사에서 합격하면 다시 옮긴다."""
    lot = an_expired_lot(planted)
    retest(planted, a_retest(lot.id))

    _process(planted, _ask(planted, lot.id, 100.0))
    assert _balances(planted, lot.id) == {_RAW: 400.0, _PRODUCTION: 100.0}


def test_a_lot_without_an_expiry_never_expires(planted: Session) -> None:
    lot = a_live_lot(planted, expires_in=None)
    _process(planted, _ask(planted, lot.id, 100.0))
    assert _balances(planted, lot.id) == {_RAW: 400.0, _PRODUCTION: 100.0}


def test_a_lot_thrown_away_by_a_retest_is_named_as_expired(planted: Session) -> None:
    """**떨어진 로트는 만료된 로트다** — 재검사는 만료된 로트만 받고, 떨어지면 만료일을 갱신하지
    않는다. 원재료창고가 비었다는 말보다 먼저 나간다 — 트리거가 묻는 순서다."""
    lot = an_expired_lot(planted)
    retest(planted, a_retest(lot.id, moisture=0.9))
    request_id = _ask(planted, lot.id, 1.0)

    assert _refused(lambda: _process(planted, request_id)) == (
        TransferClosureRefusal.LOT_HAS_EXPIRED
    )


def test_the_names_shared_with_other_paths_mean_the_same() -> None:
    """**겹치는 이름은 같은 값이다**(ADR 0014) — 부르는 쪽이 경로를 가리지 않고 한 분기로
    읽는다."""
    assert (
        TransferRequestRefusal.UNKNOWN_LOT
        == RetestRefusal.UNKNOWN_LOT
        == LotRefusal.UNKNOWN_LOT
    )


@pytest.mark.parametrize("ahead", ["request", "closure"])
def test_a_transfer_stamped_in_the_future_stops_the_site_clock(
    planted: Session, ahead: str
) -> None:
    """**요청 시각과 종결 시각도 현장 시계가 묻는 칸이다**(ADR 0019) — 미래에 적힌 줄은 시계의
    바탕이 갈렸다는 뜻이다. 그 칸을 빠뜨리면 뜰 때 아무 말이 없다."""
    lot = a_live_lot(planted)
    now = clock.now()
    later = now + timedelta(hours=1)
    request = StockTransferRequest(
        lot_id=lot.id,
        quantity=1.0,
        requested_at=later if ahead == "request" else now,
        requested_by="생산 1",
    )
    planted.add(request)
    planted.flush()
    if ahead == "closure":
        planted.add(
            StockTransferClosure(
                request_id=request.id,
                closure_type=codes.CLOSURE_CANCELLED,
                lot_id=lot.id,
                quantity=1.0,
                requested_at=now,
                closed_at=later,
                closed_by="생산 1",
            )
        )
        planted.flush()

    assert latest_stamp(planted) == later
    with pytest.raises(clock.SiteClockError, match="보다 뒤다"):
        assert_the_site_clock_holds(planted, now=now)


# ── 경계 — 쓰기 경로와 트리거가 같은 날을 가른다 ──────────────────────────


def _by_hand(session: Session, request_id: int, at: datetime) -> None:
    """쓰기 경로를 거치지 않고 처리 종결 · 원장 두 줄을 그대로 넣는다."""
    request = session.get(StockTransferRequest, request_id)
    assert request is not None
    lot = session.get(Lot, request.lot_id)
    assert lot is not None
    closure = StockTransferClosure(
        request_id=request.id,
        closure_type=codes.CLOSURE_PROCESSED,
        lot_id=request.lot_id,
        quantity=request.quantity,
        requested_at=request.requested_at,
        closed_at=at,
        closed_by="자재 담당 1",
    )
    session.add(closure)
    session.flush()
    session.add_all(
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=txn_type,
            warehouse=codes.LEDGER_TYPE_WAREHOUSES[txn_type],
            item_type=lot.item_type,
            quantity=request.quantity,
            occurred_at=at,
            transfer_closure_id=closure.id,
            transfer_closure_type=closure.closure_type,
        )
        for txn_type in codes.TRANSFER_TXN_TYPES
    )
    session.flush()


@pytest.mark.parametrize(
    ("expires", "moves"),
    [(0, True), (-1, False)],
    ids=["expires-today", "expired-yesterday"],
)
def test_the_write_path_and_the_trigger_draw_the_same_expiry_line(
    planted: Session, expires: int, moves: bool
) -> None:
    """**둘이 갈리면 트리거가 이긴다 — 이름 없는 500 이다.** 같은 요청을 쓰기 경로와 SQL 로 한
    번씩 처리해 본다. 만료일 당일은 둘 다 받고, 어제 만료면 둘 다 거절한다. 재검사와 반대쪽
    경계다(ADR 0016)."""
    lot = a_live_lot(planted, expires_in=expires)
    request_id = _ask(planted, lot.id, 100.0)

    attempt = planted.begin_nested()
    if moves:
        _process(planted, request_id)
    else:
        assert _refused(lambda: _process(planted, request_id)) == (
            TransferClosureRefusal.LOT_HAS_EXPIRED
        )
    attempt.rollback()

    if moves:
        _by_hand(planted, request_id, clock.now())
    else:
        with pytest.raises(IntegrityError, match="만료된 로트는 옮기지 않는다"):
            _by_hand(planted, request_id, clock.now())


@pytest.mark.parametrize(("quantity", "moves"), [(300.0, True), (300.5, False)])
def test_the_write_path_and_the_trigger_count_the_same_warehouse(
    planted: Session, quantity: float, moves: bool
) -> None:
    """**잔량도 같은 셈이다** — 나뉜 로트(원재료창고 300 · 생산창고 200)에서 원재료창고의 잔량
    전부는 둘 다 받고, 그보다 조금이라도 많으면 둘 다 거절한다."""
    lot = a_live_lot(planted)
    _process(planted, _ask(planted, lot.id, 200.0))
    request_id = _ask(planted, lot.id, quantity)

    attempt = planted.begin_nested()
    if moves:
        _process(planted, request_id)
    else:
        assert _refused(lambda: _process(planted, request_id)) == (
            TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS
        )
    attempt.rollback()

    if moves:
        _by_hand(planted, request_id, clock.now())
    else:
        with pytest.raises(IntegrityError, match="잔량"):
            _by_hand(planted, request_id, clock.now())


# ── 반품 — 원재료창고의 잔량만 돌려보낸다 ──────────────────────────────────


@pytest.mark.parametrize(("quantity", "returns"), [(300.0, True), (300.5, False)])
def test_a_return_counts_only_what_is_left_in_the_raw_warehouse(
    planted: Session, quantity: float, returns: bool
) -> None:
    """**생산창고로 옮긴 분량은 돌려보내지 않는다**(`PRD.md` 「착공에서 답을 받은 것」) — 로트
    전체에 500 이 있어도 원재료창고에 300 이면 그것까지만 돌려보낸다. 이름은 이동 전의 것
    그대로다(`more_than_the_lot_holds`)."""
    lot = a_live_lot(planted)
    _process(planted, _ask(planted, lot.id, 200.0))
    assert lot.inspection_id is not None

    if returns:
        return_to_supplier(planted, _from_the_lot(lot.inspection_id, quantity))
        assert _balances(planted, lot.id) == {_RAW: 0.0, _PRODUCTION: 200.0}
    else:
        with pytest.raises(RefusedReturn) as refused:
            return_to_supplier(planted, _from_the_lot(lot.inspection_id, quantity))
        assert refused.value.code == ReturnRefusal.MORE_THAN_THE_LOT_HOLDS


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


@contextmanager
def _committed_schema(engine: Engine, name: str) -> Iterator[tuple[Engine, int]]:
    """커밋이 실제로 일어나는 스키마와 그 안의 살아 있는 로트(원재료창고 500) 하나."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={name}"}, poolclass=NullPool
    )
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            plant_transfer_data(session)
            lot_id = a_live_lot(session).id
            session.commit()
        yield scoped, lot_id
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _race(
    scoped: Engine,
    first_write: Callable[[Session], None],
    second_write: Callable[[Session], None],
) -> object:
    """첫째가 잡은 채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를 커밋한다 —
    `tests/test_retest_path.py` 의 같은 이름 함수와 같은 자리다."""
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
            except (RefusedTransfer, IntegrityError) as error:
                second.rollback()
                outcome["second"] = error

        racer = threading.Thread(target=go)
        racer.start()
        deadline = time.monotonic() + 10
        waited = False
        with scoped.connect() as watcher:
            while racer.is_alive() and time.monotonic() < deadline:
                waiting = watcher.execute(
                    text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                ).scalar_one_or_none()
                if waiting == "Lock":
                    waited = True
                    break
                time.sleep(0.02)
        assert waited, "둘째가 잠금을 기다리지 않았다 — 줄을 서지 않고 지나갔다"
        first.commit()
        racer.join(10)
        assert not racer.is_alive(), "둘째가 끝나지 않았다"
    finally:
        first.close()
        second.close()
    return outcome["second"]


def test_two_processings_of_one_lot_at_once_the_second_is_named(engine: Engine) -> None:
    """**같은 로트의 두 처리는 로트 줄에서 줄을 선다** — 둘째는 첫째가 커밋한 뒤의 원재료창고를
    보고 이름을 받는다. 트리거의 500 이 아니다."""
    with _committed_schema(engine, "transfer_path_race_lot") as (scoped, lot_id):
        with Session(scoped) as session:
            requests = [_ask(session, lot_id, 300.0), _ask(session, lot_id, 300.0)]
            session.commit()

        def process_first(session: Session) -> None:
            _process(session, requests[0])

        def process_second(session: Session) -> None:
            _process(session, requests[1])

        second = _race(scoped, process_first, process_second)

        assert isinstance(second, RefusedTransfer), second
        assert second.code == TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (codes.CLOSURE_PROCESSED, TransferClosureRefusal.REQUEST_IS_ALREADY_PROCESSED),
        (codes.CLOSURE_CANCELLED, TransferClosureRefusal.REQUEST_IS_ALREADY_CANCELLED),
    ],
    ids=["processed-first", "cancelled-first"],
)
def test_processing_and_cancelling_one_request_at_once_the_second_is_named(
    engine: Engine, first: str, expected: TransferClosureRefusal
) -> None:
    """**같은 요청의 처리와 취소는 요청 줄에서 줄을 선다** — 둘째는 첫째의 종결을 보고 이름을
    받는다. 잠그지 않으면 유일키에서 진다(500)."""
    then = (
        codes.CLOSURE_CANCELLED if first == codes.CLOSURE_PROCESSED else codes.CLOSURE_PROCESSED
    )
    with _committed_schema(engine, f"transfer_path_race_{expected.value[11:30]}") as (
        scoped,
        lot_id,
    ):
        with Session(scoped) as session:
            request_id = _ask(session, lot_id, 100.0)
            session.commit()

        def close_first(session: Session) -> None:
            _close(session, request_id, first)

        def close_then(session: Session) -> None:
            _close(session, request_id, then)

        second = _race(scoped, close_first, close_then)

        assert isinstance(second, RefusedTransfer), second
        assert second.code == expected
