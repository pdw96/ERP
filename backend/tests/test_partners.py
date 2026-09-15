"""거래처와 공급사별 품목 — 조각 4."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.master import SupplierItem
from tests.factories import (
    add_code,
    make_item,
    make_partner,
    make_supplier_item,
    prepare_item_codes,
)


@pytest.fixture
def prepared(session: Session) -> Session:
    prepare_item_codes(session)
    return session


def test_a_customer_cannot_supply_an_item(prepared: Session) -> None:
    """고객사에게 발주할 수는 없다.

    `partner_type` 을 복합 외래키의 절반으로 두어 **거래처의 유형과 다를 수
    없게** 하고, CHECK 로 그 값이 공급사임을 못박는다. 둘 중 하나만 있으면
    「고객사인데 공급사라고 적은 줄」이나 「공급사가 아닌 거래처를 가리키는
    줄」이 선다.
    """
    customer = make_partner(codes.CUSTOMER, code="CUS-01")
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([customer, raw])
    prepared.flush()

    prepared.add(make_supplier_item(customer, raw))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_supplier_supplies_an_item(prepared: Session) -> None:
    """정상 경로 — 공급사 하나가 자재 하나를 댄다."""
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, lead_time_hours=120.0))
    prepared.flush()

    row = prepared.query(SupplierItem).one()
    assert row.lead_time_hours == 120.0
    assert row.partner.name == "시험 거래처"


def test_the_conversion_factor_cannot_be_zero(prepared: Session) -> None:
    """0 이면 아무리 발주해도 재고가 0 만큼 들어온다.

    단위를 바꾸는 경계가 여기 하나뿐이므로, 이 계수가 틀리면 **원장 전체의
    수량이 틀린다** — 그리고 조용히 틀린다.
    """
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, conversion_factor=0.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_conversion_factor_cannot_be_negative(prepared: Session) -> None:
    """음수면 발주할수록 재고가 줄어든다."""
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, conversion_factor=-1.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_purchase_unit_may_differ_from_the_stock_unit(prepared: Session) -> None:
    """포대로 사서 킬로그램으로 센다 — 경계가 여기 하나뿐이다."""
    add_code(prepared, codes.UOM, "BAG", "포대")
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL, stock_uom="KG")
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, purchase_uom="BAG", conversion_factor=25.0))
    prepared.flush()

    row = prepared.query(SupplierItem).one()
    assert row.purchase_uom == "BAG"
    assert row.item.stock_uom == "KG"
    assert row.conversion_factor == 25.0


def test_an_unknown_purchase_unit_is_refused(prepared: Session) -> None:
    """구매 단위도 공통코드다 — 모르는 단위로는 환산할 수 없다."""
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, purchase_uom="드럼"))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_lead_time_cannot_be_negative(prepared: Session) -> None:
    """음수면 발주일이 필요일보다 뒤가 된다 — 역산이 거꾸로 돈다."""
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw, lead_time_hours=-1.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_an_unknown_partner_type_is_refused(prepared: Session) -> None:
    """공급사와 고객사 둘뿐이다 — 유형이 흐름의 어느 쪽에 서는지를 정한다."""
    partner = make_partner()
    partner.partner_type = "협력사"
    prepared.add(partner)

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_partner_is_turned_off_not_deleted(prepared: Session) -> None:
    """거래가 끝나도 지우지 않는다 — 과거 발주와 출하가 이것을 가리킨다."""
    supplier = make_partner(codes.SUPPLIER)
    prepared.add(supplier)
    prepared.flush()
    assert supplier.is_active is True

    supplier.is_active = False
    prepared.flush()

    assert prepared.get(type(supplier), supplier.id) is not None


def test_the_same_supplier_cannot_list_an_item_twice(prepared: Session) -> None:
    """한 공급사가 한 품목에 대해 리드타임을 둘 가질 수 없다."""
    supplier = make_partner(codes.SUPPLIER)
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add_all([supplier, raw])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, raw))
    prepared.flush()
    prepared.add(make_supplier_item(supplier, raw, lead_time_hours=1.0))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_only_raw_materials_can_be_purchased(prepared: Session) -> None:
    """**공급사에게 사는 것은 원자재뿐이다.**

    완제품에 공급사를 붙이면 발주는 되는데 입고에서 로트를 만들 수 없다 —
    로트가 「공급사 출처는 원자재」를 이미 강제하기 때문이다. 받을 수 없는
    구매 마스터가 서는 것을 여기서 막는다.
    """
    supplier = make_partner(codes.SUPPLIER)
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA")
    prepared.add_all([supplier, finished])
    prepared.flush()

    prepared.add(make_supplier_item(supplier, finished, purchase_uom="EA"))
    with pytest.raises(IntegrityError):
        prepared.flush()
