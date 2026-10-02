"""반품 쓰기 경로 — 3단계 조각 2. **돌려보낸 것이 원장에서 빠진다.**

조각 1 이 표와 트리거를 세웠고, 이 조각은 그것을 **한 트랜잭션으로 부르는 자리**다.
그래서 여기서 검사하는 것은 —

- **재고 로트 반품은 문서와 원장 줄이 함께 서는가**, 불합격분은 문서만 서는가
- **트리거가 막는 것을 쓰기 경로가 먼저 이름으로 막는가** — 제약 이름이 담긴 500 이
  아니라 까닭이 담긴 거절이 나가야 한다
- **두 반품이 동시에 와도 둘째가 이름을 받는가** — 쓰기 경로가 트리거와 같은 순서로
  잠그지 않으면 둘째는 묻는 순간의 합을 보고 통과해 트리거의 500 을 맞는다

트리거 자체(잔량 · 합 · 고치지 않는다)는 `tests/test_purchase_returns.py` 가 본다.
"""

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core import codes
from app.db.base import Base
from app.db.code_attributes import TxnTypeAttribute
from app.db.inspection import Inspection
from app.db.inventory import Lot, PurchaseReturn, StockLedgerEntry
from app.services.incoming import IncomingInspection, Measurement, receive
from app.services.returns import (
    IncomingReturn,
    RefusedReturn,
    ReturnRefusal,
    return_to_supplier,
)
from tests.factories import add_code
from tests.test_write_path import (
    _FOREIGN_REASON,
    _GRAIN,
    _MOISTURE,
    RECEIVED,
    plant_master_data,
)

IN_KIND, IN_MONEY = "대물", "대금"
# 관문 1 의 규칙 표에 없는 사유 — 공통코드로는 있다.
NOT_AT_THIS_GATE = "FQ-ADH"


def plant_return_codes(session: Session) -> None:
    """반품이 기대는 기준정보 — 정산 구분과 구매반품출고의 방향."""
    add_code(session, codes.SETTLE_TYPE, IN_KIND, "대물정산")
    add_code(session, codes.SETTLE_TYPE, IN_MONEY, "대금정산")
    add_code(session, codes.TXN_TYPE, codes.TXN_PURCHASE_RETURN)
    add_code(session, codes.NC_REASON, NOT_AT_THIS_GATE, "접착력")
    session.flush()
    session.add(
        TxnTypeAttribute(
            code=codes.TXN_PURCHASE_RETURN,
            total_effect=codes.EFFECT_DECREASE,
            source_document_type="구매반품관리",
        )
    )
    session.flush()


@pytest.fixture
def planted(session: Session) -> Session:
    plant_master_data(session)
    plant_return_codes(session)
    return session


def _judged(
    session: Session, *, quantity: float = 500.0, grain: float = 30.0, **extra: object
) -> int:
    """관문 1 을 지나간 검사 하나 — 입도가 규격(10~50) 밖이면 불합격이다."""
    judged = receive(
        session,
        IncomingInspection(
            item_code="RM-01",
            supplier_code="SUP-01",
            supplier_lot_number="SL-2026-0001",
            quantity=quantity,
            judged_by="검사원 1",
            received_date=RECEIVED,
            measurements=(Measurement(_GRAIN, grain), Measurement(_MOISTURE, 0.3)),
            **extra,  # type: ignore[arg-type]
        ),
    )
    return judged.inspection_id


def _passed(session: Session, quantity: float = 500.0) -> int:
    return _judged(session, quantity=quantity)


def _failed(session: Session, quantity: float = 200.0) -> int:
    return _judged(session, quantity=quantity, grain=99.0)


def _back(inspection_id: int, quantity: float, **overrides: object) -> IncomingReturn:
    fields: dict[str, object] = {
        "inspection_id": inspection_id,
        "settle_type": IN_KIND,
        "quantity": quantity,
        "returned_by": "자재 담당 1",
    }
    fields.update(overrides)
    return IncomingReturn(**fields)  # type: ignore[arg-type]


def _from_the_lot(inspection_id: int, quantity: float, **overrides: object) -> IncomingReturn:
    return _back(
        inspection_id, quantity, **({"nonconformity_code": _FOREIGN_REASON} | overrides)
    )


def _balance(session: Session, inspection_id: int) -> float:
    lot = session.scalars(select(Lot).where(Lot.inspection_id == inspection_id)).one()
    return float(
        session.execute(
            text(
                "SELECT coalesce(sum(CASE a.total_effect WHEN :up THEN e.quantity"
                " WHEN :down THEN -e.quantity END), 0)"
                " FROM stock_ledger_entries e JOIN txn_type_attributes a"
                " ON a.group_code = e.txn_type_group AND a.code = e.txn_type"
                " WHERE e.lot_id = :lot"
            ),
            {"up": codes.EFFECT_INCREASE, "down": codes.EFFECT_DECREASE, "lot": lot.id},
        ).scalar_one()
    )


def _refused(session: Session, request: IncomingReturn) -> ReturnRefusal:
    with pytest.raises(RefusedReturn) as refused:
        return_to_supplier(session, request)
    return ReturnRefusal(refused.value.code)


# ── 재고 로트는 원장에서 빠지고, 불합격분은 문서만 선다 ─────────────────────


def test_a_lot_return_takes_one_ledger_line(planted: Session) -> None:
    """**문서와 원장 줄이 함께 선다** — 같은 로트 · 같은 수량 · 같은 시각."""
    inspection_id = _passed(planted)

    returned = return_to_supplier(planted, _from_the_lot(inspection_id, 120.0))

    document = planted.get(PurchaseReturn, returned.purchase_return_id)
    entry = planted.get(StockLedgerEntry, returned.ledger_entry_id)
    assert document is not None and entry is not None
    assert entry.txn_type == codes.TXN_PURCHASE_RETURN
    assert entry.purchase_return_id == document.id
    assert (entry.lot_id, entry.quantity, entry.occurred_at) == (
        document.lot_id,
        document.quantity,
        document.returned_at,
    )
    assert document.nonconformity_code == _FOREIGN_REASON
    assert _balance(planted, inspection_id) == 380.0


def test_a_failed_return_takes_no_ledger_line(planted: Session) -> None:
    """**불합격분은 재고가 된 적이 없다**(원칙 ①) — 문서만 서고 사유는 검사가 든다."""
    inspection_id = _failed(planted)

    returned = return_to_supplier(planted, _back(inspection_id, 200.0, settle_type=IN_MONEY))

    assert returned.ledger_entry_id is None
    document = planted.get(PurchaseReturn, returned.purchase_return_id)
    assert document is not None
    assert (document.lot_id, document.nonconformity_code) == (None, None)
    assert document.inspection_result == codes.JUDGMENT_FAILED
    assert planted.scalar(select(func.count()).select_from(StockLedgerEntry)) == 0


def test_a_lot_taken_by_special_acceptance_goes_back_like_any_lot(planted: Session) -> None:
    """특채 로트도 재고다 — 돌려보내면 원장에서 빠진다."""
    inspection_id = _judged(
        planted, nonconformity_code=_FOREIGN_REASON, special_acceptance=True
    )
    assert planted.get(Inspection, inspection_id).result == codes.JUDGMENT_SPECIAL  # type: ignore[union-attr]

    returned = return_to_supplier(planted, _from_the_lot(inspection_id, 500.0))

    assert returned.ledger_entry_id is not None
    assert _balance(planted, inspection_id) == 0.0


def test_a_lot_can_go_back_in_pieces_down_to_nothing(planted: Session) -> None:
    """**사람이 넣은 수끼리의 합이 맞는다.** `double precision` 으로 빼면 100 − 64.4 −
    35.6 이 0 이 아니라 −7.1e-15 가 되어, 다 빠지는 마지막 반품을 쓰기 경로가 거절한다.

    **수를 고른 까닭** — 처음 쓴 33.3 · 66.7 은 `double` 로도 0 이 되어, 셈을 `double`
    로 바꿔도 이 검사가 초록이었다(어긋내 확인했다).
    """
    inspection_id = _passed(planted, quantity=100.0)

    return_to_supplier(planted, _from_the_lot(inspection_id, 64.4))
    return_to_supplier(planted, _from_the_lot(inspection_id, 35.6))

    assert _refused(planted, _from_the_lot(inspection_id, 0.001)) == (
        ReturnRefusal.MORE_THAN_THE_LOT_HOLDS
    )


# ── 트리거가 막는 것을 먼저 이름으로 막는다 ────────────────────────────────


def test_an_inspection_nobody_wrote_is_named(planted: Session) -> None:
    assert _refused(planted, _back(999_999, 1.0)) == ReturnRefusal.UNKNOWN_INSPECTION


def test_a_settle_type_nobody_defined_is_named(planted: Session) -> None:
    inspection_id = _failed(planted)

    assert _refused(planted, _back(inspection_id, 1.0, settle_type="외상")) == (
        ReturnRefusal.UNKNOWN_SETTLE_TYPE
    )


def test_a_lot_return_says_why(planted: Session) -> None:
    """재고 로트는 검사가 합격시킨 것이라 **왜 돌려보내는지는 그 검사에 없다.**"""
    inspection_id = _passed(planted)

    assert _refused(planted, _back(inspection_id, 1.0)) == ReturnRefusal.REASON_IS_MISSING


def test_a_failed_return_does_not_say_why_twice(planted: Session) -> None:
    """**같은 사실을 두 곳에 적지 않는다**(원칙 ⑥) — 불합격 검사가 사유를 이미 든다."""
    inspection_id = _failed(planted)

    assert _refused(planted, _back(inspection_id, 1.0, nonconformity_code=_FOREIGN_REASON)) == (
        ReturnRefusal.REASON_COMES_WITH_A_FAILED_INSPECTION
    )


def test_a_lot_return_uses_a_reason_the_incoming_gate_knows(planted: Session) -> None:
    """공통코드에 있다는 것만으로는 안 된다 — 사 온 자재를 완제품 사유로 돌려보내지 않는다."""
    inspection_id = _passed(planted)

    assert _refused(
        planted, _from_the_lot(inspection_id, 1.0, nonconformity_code=NOT_AT_THIS_GATE)
    ) == (ReturnRefusal.REASON_IS_NOT_USABLE_AT_THIS_GATE)


def test_a_lot_does_not_give_back_more_than_it_holds(planted: Session) -> None:
    """**앞서 돌려보낸 것까지 센다** — 남은 것까지는 받고 그보다 많으면 이름으로 거절한다."""
    inspection_id = _passed(planted)
    return_to_supplier(planted, _from_the_lot(inspection_id, 300.0))

    assert _refused(planted, _from_the_lot(inspection_id, 200.5)) == (
        ReturnRefusal.MORE_THAN_THE_LOT_HOLDS
    )
    return_to_supplier(planted, _from_the_lot(inspection_id, 200.0))
    assert _balance(planted, inspection_id) == 0.0


def test_failed_returns_do_not_add_up_past_what_came(planted: Session) -> None:
    """불합격분은 원장 밖이라 **반품 문서끼리의 합**이 받은 수량을 넘지 않는다."""
    inspection_id = _failed(planted, quantity=200.0)
    return_to_supplier(planted, _back(inspection_id, 150.0))

    assert _refused(planted, _back(inspection_id, 50.5)) == ReturnRefusal.MORE_THAN_WAS_REJECTED
    return_to_supplier(planted, _back(inspection_id, 50.0))


def test_a_refusal_leaves_nothing_behind(planted: Session) -> None:
    """거절은 문서도 줄도 남기지 않는다 — 막는 것이 넣기 **전**이다."""
    inspection_id = _passed(planted)

    _refused(planted, _from_the_lot(inspection_id, 501.0))

    assert planted.scalar(select(func.count()).select_from(PurchaseReturn)) == 0
    assert _balance(planted, inspection_id) == 500.0


# ── 동시에 — 두 연결 ────────────────────────────────────────────────────────


@contextmanager
def _committed_schema(engine: Engine, name: str) -> Iterator[Engine]:
    """커밋이 실제로 일어나는 스키마 하나 — 테스트 세션의 롤백 안에서는 잠금을 잴 수 없다."""
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{name}"'))
    scoped = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={name}"}, poolclass=NullPool
    )
    try:
        Base.metadata.create_all(scoped)
        with Session(scoped) as session:
            plant_master_data(session)
            plant_return_codes(session)
            session.commit()
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))


def _race(scoped: Engine, write: Callable[[Session], object]) -> object:
    """**첫째가 잡은 채로 둘째를 보내고, 둘째가 기다리기 시작한 뒤에 첫째를 커밋한다.**

    `tests/test_purchase_returns.py` 의 같은 이름과 같은 순서다 — 둘째가 기다리는지를
    보지 않고 커밋하면 둘째가 첫째의 커밋 **뒤에** 출발했을 때 잠금이 없어도 통과한다.
    다른 것은 둘째가 받는 것을 **무엇이든** 돌려준다는 것 하나다 — 이 검사가 가르는
    것이 「이름(`RefusedReturn`)인가 트리거의 말(`IntegrityError`)인가」이기 때문이다.
    """
    first = Session(scoped)
    second = Session(scoped)
    outcome: dict[str, object] = {}
    try:
        write(first)
        pid = second.execute(text("SELECT pg_backend_pid()")).scalar_one()

        def go() -> None:
            try:
                write(second)
                second.commit()
                outcome["second"] = "committed"
            except Exception as error:  # 무엇을 받았는지가 이 검사의 답이다
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
        first.commit()
        racer.join(10)
        assert not racer.is_alive(), "둘째가 끝나지 않았다"
    finally:
        first.close()
        second.close()
    return outcome["second"]


def test_two_lot_returns_at_once_leave_the_second_with_a_name(engine: Engine) -> None:
    """**같은 잔량을 본 둘째가 트리거의 500 이 아니라 이름을 받는다.**

    쓰기 경로가 묻기 전에 잠그지 않으면 둘째는 「500 이 있다」를 보고 통과한 뒤 넣는
    자리에서 트리거에 막힌다 — 데이터는 지켜지지만 부르는 쪽은 제약 이름이 담긴 500 을
    받는다.
    """
    with _committed_schema(engine, "return_path_race") as scoped:
        with Session(scoped) as session:
            inspection_id = _passed(session)
            session.commit()

        second = _race(
            scoped,
            lambda session: return_to_supplier(session, _from_the_lot(inspection_id, 300.0)),
        )

        assert isinstance(second, RefusedReturn), second
        assert second.code == ReturnRefusal.MORE_THAN_THE_LOT_HOLDS
        with Session(scoped) as session:
            assert _balance(session, inspection_id) == 200.0


def test_two_failed_returns_at_once_leave_the_second_with_a_name(engine: Engine) -> None:
    """원장 밖의 합도 같다 — 쓰기 경로가 그 검사 줄을 먼저 잠근다."""
    with _committed_schema(engine, "failed_return_path_race") as scoped:
        with Session(scoped) as session:
            inspection_id = _failed(session, quantity=200.0)
            session.commit()

        second = _race(
            scoped,
            lambda session: return_to_supplier(session, _back(inspection_id, 150.0)),
        )

        assert isinstance(second, RefusedReturn), second
        assert second.code == ReturnRefusal.MORE_THAN_WAS_REJECTED
