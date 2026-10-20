"""재고이동 — 원재료창고의 로트를 생산창고로 옮기는 요청 · 처리 · 취소(4단계).

**합격은 로트를 만들 뿐 옮기지 않는다. 옮기는 것은 요청과 처리다**(원칙 ②).

- **요청**은 의도다 — 어느 로트를 얼마나. 재고를 잡지 않으므로 잔량도 만료도 묻지 않는다
  (`StockTransferRequest`). 시각은 서버가 「지금」으로 적는다(ADR 0019)
- **종결**은 요청 하나에 하나다 — 처리 또는 취소(ADR 0023). 처리는 종결 · 원재료창고의
  `생산출고` · 생산창고의 `생산입고` 세 줄이 한 트랜잭션이고, 로트와 수량은 요청에서 끌어온다
  (부분 처리 없음). 취소는 원장을 건드리지 않는다. 취소자는 누구든 된다 — 요청자와 견주지
  않는다(소유자, 2026-10-19)

### 데이터베이스가 막는 것을 먼저 이름으로 막는다

잔량(로트 × 창고) · 만료 · 종결 중복은 데이터베이스가 지킨다 — 원장의 잔량 트리거(ADR 0013),
종결의 만료 트리거, 종결의 요청 유일키. 여기서 같은 것을 먼저 묻는 것은 **부르는 쪽이 제약
이름 대신 까닭을 받게** 하려는 것이고, 지키는 것은 여전히 데이터베이스다 — 이 가드들을 지워도
데이터는 틀리지 않는다.

**잠그는 순서는 요청 줄 → 로트 줄이다.** 같은 요청의 처리와 취소가 동시에 오면 요청 줄에서
줄을 서고, 둘째는 첫째의 종결을 보고 이름을 받는다 — 잠그지 않으면 둘째는 유일키에서 진다
(500). 같은 로트의 두 처리는 로트 줄에서 줄을 선다 — 원장의 잔량 트리거가 잡는 그 줄이고
같은 잠금(`FOR NO KEY UPDATE`)이다. 로트 줄을 먼저 잡고 요청 줄을 잡는 경로는 없다.

### 거절의 이름은 경로마다 열거 하나다 (ADR 0014)

요청과 종결은 경로가 둘이라 열거도 둘이다. **겹치는 이름은 같은 값이다** — `unknown_lot` 은
재검사 · 로트 읽기와 같다.

**원재료창고의 잔량을 넘는 처리는 `more_than_the_raw_warehouse_holds` 다.** 반품은 같은 셈을
`more_than_the_lot_holds` 로 말한다 — 그 이름이 이동보다 먼저 나갔고, 고치면 있는 이름이
바뀌는 깨는 변경이다. 이동은 처음 서는 경로라 셈 그대로의 이름을 단다. 로트를 읽는 응답의
`balance` 는 모든 창고의 합이라, 「로트에 남은 것」이라 말하면 부르는 쪽이 그 수와 견준다.

**이 경로가 못 보는 부류**(W-6 ③) —

- **원자재가 아닌 로트 · 입고 줄이 없는 로트의 요청.** 지금 로트를 짓는 길은 관문 1 하나라
  원자재이고 입고 줄과 함께 선다(`incoming.receive`). 그런 로트는 쓰기 경로 밖에서만 서고,
  그 요청은 요청 트리거가 막는다(500) — 닿지 않는 가드를 세우지 않았다(NC-129)
- **같은 요청 본문을 두 번 보내는 것.** 요청이 둘 선다. 요청은 재고를 잡지 않아 잔량은
  안전하다 — 멱등 키는 없다(설계 ② 「보장하지 않는 것」)
- **시계가 거꾸로 간 처리.** 요청보다 앞선 종결 · 입고보다 앞선 요청은 서버가 「지금」을
  적으므로 이 경로에서는 나지 않는다. 시계가 거꾸로 가면 CHECK · 트리거가 막고, 그 말은 500 이다
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock, codes
from app.db.inspection import Inspection
from app.db.inventory import Lot, StockLedgerEntry, StockTransferClosure, StockTransferRequest
from app.services.returns import goes_below_zero


class TransferRequestRefusal(StrEnum):
    """이동 요청을 거절할 때 `detail[].type` 으로 나가는 이름 — **목록이 여기 한 벌이다.**"""

    UNKNOWN_LOT = "unknown_lot"


class TransferClosureRefusal(StrEnum):
    """이동 요청을 처리 · 취소할 때 `detail[].type` 으로 나가는 이름 — **목록이 여기 한
    벌이다.**"""

    UNKNOWN_TRANSFER_REQUEST = "unknown_transfer_request"
    REQUEST_IS_ALREADY_PROCESSED = "request_is_already_processed"
    REQUEST_IS_ALREADY_CANCELLED = "request_is_already_cancelled"
    LOT_HAS_EXPIRED = "lot_has_expired"
    MORE_THAN_THE_RAW_WAREHOUSE_HOLDS = "more_than_the_raw_warehouse_holds"


class RefusedTransfer(Exception):
    """받을 수 없는 요청 · 종결 — 모양은 `RefusedReturn` 과 같다. 메시지는 고쳐도 되고 `code` 는
    고치면 깨진다."""

    def __init__(
        self, code: TransferRequestRefusal | TransferClosureRefusal, message: str
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IncomingTransferRequest:
    """받은 이동 요청 한 건 — 어느 로트를 · 얼마나 · 누가."""

    lot_id: int
    quantity: float
    requested_by: str


@dataclass(frozen=True)
class TransferRequested:
    """요청이 선 뒤 남은 것."""

    transfer_request_id: int


@dataclass(frozen=True)
class IncomingTransferClosure:
    """받은 종결 한 건 — 어느 요청을 · 처리인가 취소인가 · 누가."""

    transfer_request_id: int
    closure_type: str
    closed_by: str


@dataclass(frozen=True)
class TransferClosed:
    """종결이 선 뒤 남은 것."""

    # 처리면 `생산출고` · `생산입고` 줄 하나씩, `codes.TRANSFER_TXN_TYPES` 의 순서로.
    # 취소면 비었다.
    ledger_entry_ids: tuple[int, ...]


def request_transfer(session: Session, request: IncomingTransferRequest) -> TransferRequested:
    """이동 요청 한 건을 세운다.

    **잠그지 않는다** — 요청 트리거도 잠그지 않는다. 로트를 지우는 쓰기 경로가 없어 「있다」는
    답이 묻는 순간과 넣는 순간 사이에 바뀌지 않는다. **부르는 쪽이 트랜잭션을 연다** —
    `flush` 까지만 한다.
    """
    if session.get(Lot, request.lot_id) is None:
        raise RefusedTransfer(
            TransferRequestRefusal.UNKNOWN_LOT, f"옮길 로트가 없다: {request.lot_id}"
        )
    row = StockTransferRequest(
        lot_id=request.lot_id,
        quantity=request.quantity,
        requested_at=clock.now(),
        requested_by=request.requested_by,
    )
    session.add(row)
    session.flush()
    return TransferRequested(row.id)


def _request(session: Session, transfer_request_id: int) -> StockTransferRequest:
    """**요청 줄을 잠근다** — 같은 요청의 종결끼리 여기서 줄을 선다.

    `key_share=True` 가 `FOR NO KEY UPDATE` 다 — 종결을 넣을 때 외래키가 요청 줄에 잡는
    `KEY SHARE` 와 부딪치지 않는다(`app/db/ledger_guards.py` 머리).
    """
    found = session.scalars(
        select(StockTransferRequest)
        .where(StockTransferRequest.id == transfer_request_id)
        .with_for_update(key_share=True)
    ).one_or_none()
    if found is None:
        raise RefusedTransfer(
            TransferClosureRefusal.UNKNOWN_TRANSFER_REQUEST,
            f"그런 이동 요청이 없다: {transfer_request_id}",
        )
    return found


def _must_still_be_open(session: Session, request: StockTransferRequest) -> None:
    """**요청 하나에 종결 하나**(ADR 0023) — 유일키가 지키는 것을 이름으로 먼저 말한다."""
    closed = session.scalars(
        select(StockTransferClosure.closure_type).where(
            StockTransferClosure.request_id == request.id
        )
    ).one_or_none()
    if closed == codes.CLOSURE_PROCESSED:
        raise RefusedTransfer(
            TransferClosureRefusal.REQUEST_IS_ALREADY_PROCESSED,
            f"이동 요청 {request.id} 는 이미 처리됐다 — 처리된 요청은 취소도 다시 처리도 되지"
            " 않는다",
        )
    if closed is not None:
        raise RefusedTransfer(
            TransferClosureRefusal.REQUEST_IS_ALREADY_CANCELLED,
            f"이동 요청 {request.id} 는 이미 취소됐다 — 옮기려면 새로 요청한다",
        )


def _live_expiry(session: Session, lot: Lot) -> date | None:
    """**지금 살아 있는 만료일** — 가장 늦게 합격한 재검사의 갱신 만료일, 없으면 로트의 기준
    만료일이다. 고르는 순서(판정 시각, 그다음 대리키)는 종결 트리거와 같다.

    트리거는 「처리 시각 이전에 판정된」 재검사만 본다. 여기서 그 조건을 두지 않는 것은 처리
    시각이 「지금」이라 그보다 늦게 판정된 재검사가 시계가 거꾸로 가지 않고는 없기 때문이다 —
    닿지 않는 조건이다(NC-129).
    """
    renewed = session.scalars(
        select(Inspection)
        .where(Inspection.target_lot_id == lot.id, Inspection.result == codes.JUDGMENT_PASSED)
        .order_by(Inspection.judged_at.desc(), Inspection.id.desc())
        .limit(1)
    ).first()
    return renewed.renewed_expiry_date if renewed is not None else lot.expiry_date


def _may_move(session: Session, request: StockTransferRequest, at: datetime) -> Lot:
    """만료와 원재료창고의 잔량을 묻는다 — 트리거가 묻는 순서다.

    만료는 종결이 들어갈 때(`stock_transfer_closure_moves_only_a_live_lot`), 잔량은 그 뒤의
    원장 줄이 들어갈 때 묻는다. 경계는 재검사와 같다 — 만료일이 그날보다 **앞설 때만** 만료다.
    만료일이 없으면 만료가 아니다.

    **로트 줄은 잔량을 세는 자리가 잠근다**(`goes_below_zero`). 만료는 그 앞에서 잠그지 않고
    읽는다 — 재검사는 만료된 로트에만 서므로, 끼어드는 재검사가 바꿀 수 있는 것은 이미
    만료로 읽힌 로트뿐이고 그 답은 거절 그대로다.
    """
    lot = session.get(Lot, request.lot_id)
    # 요청은 로트를 외래키로 가리키고, 로트를 지우는 쓰기 경로는 없다.
    assert lot is not None
    expires = _live_expiry(session, lot)
    if expires is not None and expires < at.date():
        raise RefusedTransfer(
            TransferClosureRefusal.LOT_HAS_EXPIRED,
            f"로트 {lot.lot_number} 의 만료일({expires})이 오늘({at.date()})보다 앞선다 —"
            " 만료된 로트는 옮기지 않는다. 재검사에서 합격하면 다시 옮길 수 있다",
        )
    leaves = codes.LEDGER_TYPE_WAREHOUSES[codes.TXN_TRANSFER_OUT]
    if goes_below_zero(session, lot, leaves, request.quantity):
        raise RefusedTransfer(
            TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS,
            f"로트 {lot.lot_number} 의 {leaves}창고에 남은 것보다 많이 옮기게 된다 —"
            " 모자라면 남은 만큼 새로 요청한다",
        )
    return lot


def close_transfer(session: Session, closure: IncomingTransferClosure) -> TransferClosed:
    """이동 요청 하나를 처리하거나 취소한다.

    **종결을 먼저, 원장 줄을 나중에 넣는다** — 「처리는 두 줄을 가진다」를 커밋 때 묻는 지연
    트리거(`stock_transfer_processing_has_its_ledger_lines`)가 그 순서를 받는다. **부르는 쪽이
    트랜잭션을 연다** — `flush` 까지만 한다.
    """
    request = _request(session, closure.transfer_request_id)
    _must_still_be_open(session, request)

    # **시각은 서버가 적는다** — 처리와 그 두 줄이 같은 시각을 든다(쌍 외래키).
    closed_at = clock.now()
    processing = closure.closure_type == codes.CLOSURE_PROCESSED
    lot = _may_move(session, request, closed_at) if processing else None

    row = StockTransferClosure(
        request_id=request.id,
        closure_type=closure.closure_type,
        lot_id=request.lot_id,
        quantity=request.quantity,
        requested_at=request.requested_at,
        closed_at=closed_at,
        closed_by=closure.closed_by,
    )
    session.add(row)
    session.flush()

    if lot is None:
        return TransferClosed(())

    # 요청이 선 로트는 입고 줄이 있고(요청 트리거), 입고 줄은 로트를 만든 검사와 쌍이다.
    assert lot.inspection_id is not None
    entries = [
        StockLedgerEntry(
            lot_id=lot.id,
            inspection_id=lot.inspection_id,
            txn_type=txn_type,
            warehouse=codes.LEDGER_TYPE_WAREHOUSES[txn_type],
            item_type=lot.item_type,
            quantity=request.quantity,
            occurred_at=closed_at,
            transfer_closure_id=row.id,
            transfer_closure_type=row.closure_type,
        )
        for txn_type in codes.TRANSFER_TXN_TYPES
    ]
    session.add_all(entries)
    session.flush()
    return TransferClosed(tuple(entry.id for entry in entries))
