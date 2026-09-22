"""수불 원장 — 조각 10.

**원장은 합으로 읽는 표다.** 그래서 여기서 막는 것들의 피해는 줄 하나에
그치지 않는다 — `NaN` 한 줄이 이후의 모든 잔량을 `NaN` 으로 만들고, 방향을
모르는 유형 한 줄이 더할지 뺄지를 세는 쪽에서 무너뜨린다.

**원칙 ⑦이 이 표의 모양을 정한다.** 줄을 지우거나 고치지 않고 취소는 반대
방향의 새 줄이므로, 삭제 칸도 수정 시각도 없다 — 그 **없음**을 여기서 확인한다.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import TxnTypeAttribute
from app.db.inspection import Inspection
from app.db.inventory import Lot, StockLedgerEntry
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

# 총량 영향이 「감소」인 유형 — 속성 줄은 있지만 이 조각이 내는 유형은 아니다.
OTHER_TXN_TYPE = "판매출고"


@pytest.fixture
def prepared(session: Session) -> Session:
    """로트 하나와 그 로트를 만든 검사, 그리고 수불유형 셋."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.WAREHOUSE, codes.WAREHOUSE_RAW, "원재료창고")
    for txn_type in (codes.TXN_PURCHASE_RECEIPT, OTHER_TXN_TYPE):
        add_code(session, codes.TXN_TYPE, txn_type)
    session.flush()

    session.add_all(
        [
            TxnTypeAttribute(
                code=codes.TXN_PURCHASE_RECEIPT,
                total_effect=codes.EFFECT_INCREASE,
                source_document_type="가입고",
            ),
            TxnTypeAttribute(
                code=OTHER_TXN_TYPE,
                total_effect=codes.EFFECT_DECREASE,
                source_document_type="출하 실적",
            ),
        ]
    )

    material = make_item(codes.RAW_MATERIAL, code="RM-01")
    supplier = make_partner(codes.SUPPLIER, code="SUP-01")
    session.add_all([material, supplier])
    session.flush()

    inspection = Inspection(
        item_id=material.id,
        item_type=material.item_type,
        material_group=material.material_group,
        supplier_id=supplier.id,
        supplier_type=supplier.partner_type,
        supplier_lot_number="SL-2026-0001",
        quantity=500.0,
        # **로트와 같은 날이어야 한다** — 둘을 쌍으로 묶은 외래키가 그것을 본다
        # (`fk_lot_inspection_received_date`). 같은 사실이 두 표에 사는 자리를
        # 구조로 닫은 것이라 픽스처도 그 구조를 지나간다.
        received_date=date(2026, 9, 21),
        judged_at=datetime(2026, 9, 21, 9, 0),
        judged_by="검사원 1",
        result=codes.JUDGMENT_PASSED,
    )
    session.add(inspection)
    session.flush()
    # **로트가 자기를 만든 검사를 가리킨다.** 원장의 입고 줄이 그 쌍을 가리키므로
    # 여기서 비워 두면 원장 줄이 설 자리가 없다 — 「그 로트를 만든 검사인가」를
    # 데이터베이스가 보는 자리다.
    session.add(
        Lot(
            item_id=material.id,
            item_type=material.item_type,
            lot_number="RM-01-260921-01",
            lot_origin=codes.LOT_FROM_SUPPLIER,
            warehouse=codes.WAREHOUSE_RAW,
            stock_type=codes.STOCK_GOOD,
            quantity=500.0,
            received_date=date(2026, 9, 21),
            inspection_id=inspection.id,
            inspection_result=inspection.result,
        )
    )
    session.flush()
    return session


def _entry(session: Session, **overrides: object) -> StockLedgerEntry:
    """제약을 통과하는 입고 줄 하나. 넘긴 값만 달라진다."""
    fields: dict[str, object] = {
        "lot_id": session.query(Lot).one().id,
        "inspection_id": session.query(Inspection).one().id,
        "txn_type": codes.TXN_PURCHASE_RECEIPT,
        "quantity": 500.0,
        "occurred_at": datetime(2026, 9, 21, 9, 30),
    }
    fields.update(overrides)
    return StockLedgerEntry(**fields)


# ── 줄이 선다 ───────────────────────────────────────────────────────────────


def test_a_receipt_line_names_the_judgement_it_came_from(prepared: Session) -> None:
    """**합격이 로트를 만들고 그 자리에 입고 한 줄이 남는다.**"""
    prepared.add(_entry(prepared))
    prepared.flush()

    row = prepared.query(StockLedgerEntry).one()
    assert row.txn_type == codes.TXN_PURCHASE_RECEIPT
    assert row.inspection_id == prepared.query(Inspection).one().id
    # 유형 그룹은 데이터가 아니라 구조다 — 적지 않아도 채워진다.
    assert row.txn_type_group == codes.TXN_TYPE


def test_the_quantity_is_always_positive(prepared: Session) -> None:
    """**방향은 원장이 아니라 유형이 말한다.**

    `txn_type_attributes.total_effect` 가 증가·감소를 이미 들고 있으므로 원장
    줄이 부호로 다시 말하지 않는다. 두 벌이면 「유형은 감소인데 수량이 양수인
    줄」이 서고, 그 줄을 제약이 막지 못한다.
    """
    prepared.add(_entry(prepared))
    prepared.flush()

    attribute = prepared.get(TxnTypeAttribute, (codes.TXN_TYPE, codes.TXN_PURCHASE_RECEIPT))
    assert attribute is not None
    assert attribute.total_effect == codes.EFFECT_INCREASE
    assert prepared.query(StockLedgerEntry).one().quantity > 0


def test_the_table_has_no_way_to_erase_a_line(prepared: Session) -> None:
    """**원칙 ⑦ — 일어난 일은 지우지 않는다. 취소는 새 사실이다.**

    삭제 칸도 수정 시각도 두지 않는다. 있으면 지우는 길이 생기고, 길이 있으면
    언젠가 지나간다. 그 **없음**은 주석으로만 두면 다음 사람이 칸 하나를 더하며
    지나가므로 여기서 이름으로 지킨다.
    """
    columns = {column.name for column in sa_inspect(StockLedgerEntry).columns}

    assert not {
        name
        for name in columns
        if "delete" in name or "deleted" in name or "cancel" in name or "updated" in name
    }, columns


# ── 로트 하나에 입고 줄은 하나 ─────────────────────────────────────────────


def test_a_lot_receives_only_once(prepared: Session) -> None:
    """둘이 서면 같은 물건이 두 번 들어온 것이 되어 **잔량이 실물의 두 배**가 된다."""
    prepared.add(_entry(prepared))
    prepared.flush()

    prepared.add(_entry(prepared, quantity=1.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 유형은 속성 줄을 가리킨다 ───────────────────────────────────────────────


def test_a_type_without_attributes_cannot_stand_in_the_ledger(prepared: Session) -> None:
    """공통코드를 가리켰으면 통과했을 자리다.

    **속성 줄이 없으면 총량 영향이 없고**, 그러면 잔량을 세는 쪽이 그 줄을 더해야
    하는지 빼야 하는지 모른다. 코드가 있다는 것과 쓸 수 있다는 것은 다르다.

    **다른 유형을 적어서는 이것을 확인할 수 없다.** 속성이 없는 유형은 이 조각이
    내는 유형도 아니라서 「구매입고만」 CHECK 가 **먼저** 물고, 그러면 속성
    외래키는 한 번도 불리지 않는다 — 물게 하는 제약을 직접 읽어 확인한 자리다.
    그래서 유형은 그대로 두고 **그 유형의 속성 줄을 없앤다.**
    """
    prepared.query(TxnTypeAttribute).filter_by(code=codes.TXN_PURCHASE_RECEIPT).delete()
    prepared.flush()

    prepared.add(_entry(prepared))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_another_type_cannot_be_written_yet(prepared: Session) -> None:
    """**이 조각이 내는 유형은 하나다.**

    `판매출고` 는 코드도 속성 줄도 갖춘 유형이다. 다만 그것을 내는 쪽이 출하
    단계에 있으므로, 지금 받아 두면 **근거 문서가 없는 줄**이 서고 화면에서는
    실제로 일어난 일처럼 보인다. 그 유형을 내는 조각이 설 때 CHECK 가 함께
    넓어진다.
    """
    prepared.add(_entry(prepared, txn_type=OTHER_TXN_TYPE))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 가리키는 것이 실재한다 ──────────────────────────────────────────────────


def test_a_line_cannot_point_at_a_lot_that_does_not_exist(prepared: Session) -> None:
    """원장 줄은 언제나 실재하는 로트의 사실이다."""
    prepared.add(_entry(prepared, lot_id=9999))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_receipt_cannot_stand_without_a_judgement(prepared: Session) -> None:
    """**입고 줄은 자기를 만든 검사를 가리킨다** — 비워 두면 근거 없는 입고가 선다."""
    prepared.add(_entry(prepared, inspection_id=None))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 값이 뜻을 갖는가 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_the_quantity_must_be_a_number_you_can_add(prepared: Session, bad: float) -> None:
    """**원장은 합으로 읽는 표라 한 줄의 피해가 표 하나에 그치지 않는다.**

    `NaN >= 0` 이 참이라 하한만으로는 막지 못한다. 한 줄이 들어오면 이후의 모든
    잔량이 `NaN` 이 되고 `NaN` 과의 비교는 전부 거짓이라 **재고가 조용히
    사라진다.** 음수는 부호로 방향을 말하려는 시도이며, 방향은 유형이 말한다.
    """
    prepared.add(_entry(prepared, quantity=bad))
    with pytest.raises(IntegrityError):
        prepared.flush()
