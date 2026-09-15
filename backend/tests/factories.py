"""테스트가 쓰는 최소 기준정보.

시드는 조각 7의 일이다. 여기 있는 것은 **제약을 검사하기 위해 필요한
최소한**이며, 실제 값이 아니라 자리만 채운다.
"""

from sqlalchemy.orm import Session

from app.core import codes
from app.db.common_codes import CodeGroup, CommonCode
from app.db.master import BomComponent, Item, Partner, SupplierItem

_DEFINITIONS = {group.group_code: group for group in codes.CODE_GROUPS}


def add_group(session: Session, group_code: str) -> CodeGroup:
    """공통코드 그룹 한 줄을 정의대로 넣는다."""
    definition = _DEFINITIONS[group_code]
    group = CodeGroup(
        group_code=definition.group_code,
        name=definition.name,
        value_fixed=definition.value_fixed,
        description=definition.description,
    )
    session.add(group)
    return group


def add_code(session: Session, group_code: str, code: str, name: str | None = None) -> None:
    """공통코드 한 줄. 그룹이 없으면 함께 넣는다."""
    if session.get(CodeGroup, group_code) is None:
        add_group(session, group_code)
        session.flush()
    session.add(CommonCode(group_code=group_code, code=code, name=name or code))


def prepare_item_codes(session: Session) -> None:
    """품목이 가리키는 가변 그룹의 값 — 공정과 단위."""
    add_code(session, codes.PROCESS, "배합")
    add_code(session, codes.PROCESS, "코팅")
    add_code(session, codes.UOM, "EA", "개")
    add_code(session, codes.UOM, "KG", "킬로그램")
    session.flush()


def make_item(
    item_type: str = codes.RAW_MATERIAL,
    *,
    code: str | None = None,
    stock_uom: str = "KG",
    **overrides: object,
) -> Item:
    """제약을 통과하는 품목 하나. 넘긴 값만 달라진다."""
    prefix = codes.ITEM_CODE_PREFIXES[item_type]
    fields: dict[str, object] = {
        "code": code or f"{prefix}01",
        "name": f"시험 {item_type}",
        "item_type": item_type,
        "stock_uom": stock_uom,
        "stock_uom_group": codes.UOM,
        "process_group": codes.PROCESS,
        "phase": codes.PHASE_MASS_PRODUCTION,
    }
    # 원자재만 안전재고가 필수다.
    if item_type == codes.RAW_MATERIAL:
        fields["safety_stock"] = 100.0
    fields.update(overrides)
    return Item(**fields)


def make_bom(parent: Item, child: Item, level: int, unit_quantity: float = 2.0) -> BomComponent:
    """BOM 한 줄. 유형 두 칸은 품목에서 그대로 따라온다."""
    return BomComponent(
        parent_item_id=parent.id,
        parent_item_type=parent.item_type,
        child_item_id=child.id,
        child_item_type=child.item_type,
        level=level,
        unit_quantity=unit_quantity,
    )


def make_partner(
    partner_type: str = codes.SUPPLIER, *, code: str = "SUP-01", name: str = "시험 거래처"
) -> Partner:
    """제약을 통과하는 거래처 하나."""
    return Partner(code=code, name=name, partner_type=partner_type)


def make_supplier_item(
    partner: Partner,
    item: Item,
    *,
    lead_time_hours: float = 72.0,
    purchase_uom: str = "KG",
    conversion_factor: float = 1.0,
) -> SupplierItem:
    """공급사별 품목 한 줄."""
    return SupplierItem(
        partner_id=partner.id,
        partner_type=partner.partner_type,
        item_id=item.id,
        item_type=item.item_type,
        lead_time_hours=lead_time_hours,
        purchase_uom=purchase_uom,
        purchase_uom_group=codes.UOM,
        conversion_factor=conversion_factor,
    )
