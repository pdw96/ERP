"""로트를 읽는다 — **잔량과 지금 만료일은 저장하지 않고 센다**(`docs/PRD-3단계.md` 성공 기준 7).

- **잔량**은 원장 줄의 합이다 — 방향은 유형의 `total_effect` 가 말한다. 트리거(ADR 0013)와
  같은 셈이고 같은 자릿수(`numeric`)다
- **지금 만료일**은 가장 최근에 합격한 재검사의 갱신 만료일, 없으면 라벨의 만료일이다
  (ADR 0017). 재검사 트리거와 같은 순서(판정 시각, 그다음 대리키)로 고른다
- **재검사를 기다리는 로트**는 원자재이고, 지금 만료일이 현장의 오늘보다 앞서며, 잔량이 있는
  로트다 — 재검사 쓰기 경로(`app/services/retests.py`)가 받는 것과 같은 경계다. 만료일
  당일까지는 쓸 수 있다

**잠그지 않는다.** 읽는 순간의 답이고, 그 답으로 무엇을 쓰는 쪽은 자기 경로에서 다시 묻는다.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Numeric, Row, Select, and_, case, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.core import clock, codes
from app.db.code_attributes import TxnTypeAttribute
from app.db.inspection import Inspection
from app.db.inventory import Lot, StockLedgerEntry
from app.db.master import Item

_LotQuery = Select[int, str, str, float, object, date | None, date | None, bool]


@dataclass(frozen=True)
class LotView:
    """로트 하나의 지금."""

    lot_id: int
    lot_number: str
    item_code: str
    received_quantity: float
    balance: float
    labelled_expiry_date: date | None
    current_expiry_date: date | None
    awaiting_retest: bool


@dataclass(frozen=True)
class LotPage:
    """목록의 한 쪽 — 다음 쪽이 있으면 마지막 줄의 대리키를 든다."""

    lots: tuple[LotView, ...]
    last_lot_id: int | None


def _balance() -> ColumnElement[object]:
    signed = case(
        (
            TxnTypeAttribute.total_effect == codes.EFFECT_INCREASE,
            cast(StockLedgerEntry.quantity, Numeric),
        ),
        (
            TxnTypeAttribute.total_effect == codes.EFFECT_DECREASE,
            -cast(StockLedgerEntry.quantity, Numeric),
        ),
    )
    return (
        select(func.coalesce(func.sum(signed), 0))
        .join(
            TxnTypeAttribute,
            (TxnTypeAttribute.group_code == StockLedgerEntry.txn_type_group)
            & (TxnTypeAttribute.code == StockLedgerEntry.txn_type),
        )
        .where(StockLedgerEntry.lot_id == Lot.id)
        .correlate(Lot)
        .scalar_subquery()
    )


def _current_expiry() -> ColumnElement[date | None]:
    renewed = (
        select(Inspection.renewed_expiry_date)
        .where(
            Inspection.target_lot_id == Lot.id,
            Inspection.result == codes.JUDGMENT_PASSED,
        )
        .order_by(Inspection.judged_at.desc(), Inspection.id.desc())
        .limit(1)
        .correlate(Lot)
        .scalar_subquery()
    )
    return func.coalesce(renewed, Lot.expiry_date)


def _awaiting_retest(
    balance: ColumnElement[object], current: ColumnElement[date | None], today: date
) -> ColumnElement[bool]:
    """**재검사에서 떨어진 로트는 따로 묻지 않는다** — 떨어지면 잔량 전부가 폐기 줄로 나가고
    (원장 트리거가 「폐기는 잔량 전부」를 지킨다) 그 뒤로 로트에 더해지는 줄이 없어, 잔량이 0
    이라는 조건이 그것을 덮는다. 따로 적은 조건은 어긋내도 아무 검사가 빨개지지 않았다.

    **원자재만이다** — 재검사 쓰기 경로가 받는 것과 같다. 오늘은 원자재 말고는 잔량이 있는
    로트가 설 길이 없어 이 조건을 어긋내도 빨개지지 않는다(`docs/audit/mutations.md`
    「아직 초록인 어긋냄」 — 생산 입고가 서는 단계에서 문다).
    """
    return and_(
        Item.material_group.is_not(None),
        current.is_not(None),
        current < today,
        balance > 0,
    )


def _rows(today: date) -> tuple[_LotQuery, ColumnElement[bool]]:
    balance = _balance()
    current = _current_expiry()
    awaiting = _awaiting_retest(balance, current, today)
    query = select(
        Lot.id,
        Lot.lot_number,
        Item.code,
        Lot.quantity,
        balance,
        Lot.expiry_date,
        current,
        awaiting,
    ).join(Item, Item.id == Lot.item_id)
    return query, awaiting


def _view(row: Row[int, str, str, float, object, date | None, date | None, bool]) -> LotView:
    lot_id, lot_number, item_code, quantity, balance, labelled, current, awaiting = row
    # 잔량은 `numeric` 의 합이라 `Decimal` 로 온다 — 응답은 수량 칸과 같은 `float` 이다.
    return LotView(
        lot_id=lot_id,
        lot_number=lot_number,
        item_code=item_code,
        received_quantity=quantity,
        balance=float(str(balance)),
        labelled_expiry_date=labelled,
        current_expiry_date=current,
        awaiting_retest=bool(awaiting),
    )


def look_up(session: Session, lot_id: int) -> LotView | None:
    """로트 하나 — 없으면 `None`."""
    query, _ = _rows(clock.today())
    row = session.execute(query.where(Lot.id == lot_id)).one_or_none()
    return None if row is None else _view(row)


def list_lots(
    session: Session, *, awaiting_retest: bool, after: int | None, limit: int
) -> LotPage:
    """로트 목록의 한 쪽 — **대리키 순서다**(ADR 0020).

    정렬 키가 고쳐지지 않는 대리키 하나라, 넘기는 동안 조건을 계속 채우는 줄은 겹치지도
    빠지지도 않는다. 한 줄 더 읽어 다음 쪽이 있는지 안다.
    """
    query, awaiting = _rows(clock.today())
    if awaiting_retest:
        query = query.where(awaiting)
    if after is not None:
        query = query.where(Lot.id > after)
    rows = session.execute(query.order_by(Lot.id).limit(limit + 1)).all()
    views = tuple(_view(row) for row in rows[:limit])
    more = len(rows) > limit
    return LotPage(lots=views, last_lot_id=views[-1].lot_id if more and views else None)
