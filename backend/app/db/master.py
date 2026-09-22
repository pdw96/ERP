"""전사 기준정보 — 품목과 BOM.

반제품은 **만들어지면서 쓰인다.** 표가 둘로 갈려 있으면 앉을 자리가 없으므로
완제품 · 반제품 · 원자재가 한 표에 산다. 유형에 따라 비는 칸이 생기는 것은
통합의 부작용이 아니라 **정상**이다 — 한 표라야 「이 유형에는 해당 없음」이라고
말할 수 있다.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference, is_finite, is_present


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# 코드 접두가 유형과 맞는가. 유형마다 한 갈래이며, 어느 갈래에도 맞지 않으면
# 거부된다 — 「FG- 로 시작하는 원자재」 같은 줄이 설 수 없다.
_CODE_PREFIX_MATCHES_TYPE = " OR ".join(
    f"(item_type = '{item_type}' AND code LIKE '{prefix}%')"
    for item_type, prefix in codes.ITEM_CODE_PREFIXES.items()
)

# 2단 BOM 의 두 자리. **단계가 양쪽 유형을 정한다.**
_BOM_LEVEL_MATCHES_TYPES = " OR ".join(
    f"(level = {level} AND parent_item_type = '{parent}' AND child_item_type = '{child}')"
    for level, (parent, child) in codes.BOM_LEVEL_TYPES.items()
)


class Item(Base):
    """품목 한 표 — 완제품 · 반제품 · 원자재.

    안전재고 · 유효기간 · 리드타임 계수가 한 곳에 모인다. 2단 BOM 도 납기
    역산도 전부 여기서 값을 읽는다.
    """

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(f"item_type IN ({_quoted(codes.ITEM_TYPES)})", name="ck_item_type"),
        CheckConstraint(f"phase IN ({_quoted(codes.ITEM_PHASES)})", name="ck_item_phase"),
        CheckConstraint(_CODE_PREFIX_MATCHES_TYPE, name="ck_item_code_prefix"),
        CheckConstraint(is_present("code"), name="ck_item_code_is_present"),
        CheckConstraint(is_present("name"), name="ck_item_name_is_present"),
        # 「반제품은 유효기간을 두지 않고 제품만 유효기간을 정한다.」 표가
        # 하나여서 이 규칙을 제약으로 적을 수 있게 됐다.
        CheckConstraint(
            f"item_type <> '{codes.SEMI_FINISHED}' OR shelf_life_days IS NULL",
            name="ck_item_semi_finished_has_no_shelf_life",
        ),
        # 원자재의 안전재고는 비어 있으면 안 된다. 자재 리스크가 이 값을 재고와
        # 곧바로 견주므로 비면 비교 자체가 성립하지 않는다. 완제품은 아직 값을
        # 정한 사람이 없어 비어 있는 것이 맞다 — **없는 값을 지어내지 않는다.**
        CheckConstraint(
            f"item_type <> '{codes.RAW_MATERIAL}' OR safety_stock IS NOT NULL",
            name="ck_item_raw_material_has_safety_stock",
        ),
        # 음수를 넣으면 소요 시간이 음수가 되고 착수를 **완료보다 뒤에** 잡는다
        # — 계획이 시간을 거꾸로 흐르게 한다.
        CheckConstraint(
            f"setup_hours IS NULL OR (setup_hours >= 0 AND {is_finite('setup_hours')})",
            name="ck_item_setup_hours",
        ),
        CheckConstraint(
            f"hours_per_unit IS NULL"
            f" OR (hours_per_unit >= 0 AND {is_finite('hours_per_unit')})",
            name="ck_item_hours_per_unit",
        ),
        CheckConstraint(
            "shelf_life_days IS NULL OR shelf_life_days > 0", name="ck_item_shelf_life"
        ),
        CheckConstraint(
            f"safety_stock IS NULL OR (safety_stock >= 0 AND {is_finite('safety_stock')})",
            name="ck_item_safety_stock",
        ),
        # `id` 는 이미 기본키라 이 유일키가 행을 더 좁히지 않는다. 두는 이유는
        # **복합 외래키의 상대가 되기 위해서**다 — 「이 BOM 줄의 상위는
        # 완제품이어야 한다」를 참조하는 쪽에서 걸려면 `(id, 유형)` 쌍을 가리킬
        # 수 있어야 한다. 덤으로 유형을 나중에 바꾸는 것도 막힌다.
        UniqueConstraint("id", "item_type", name="uq_item_id_type"),
        # 공정과 재고 단위는 **공통코드를 가리킨다.** 허용값을 파이썬 상수에서
        # 구워 CHECK 로 박으면, 늘 수 있다고 선언한 그룹이 실제로는 얼어붙는다
        # — 운영자가 단위 하나를 더해도 그 단위를 쓰는 품목이 거부된다.
        ForeignKeyConstraint(
            ["process_group", "process"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_item_process",
        ),
        ForeignKeyConstraint(
            ["stock_uom_group", "stock_uom"],
            ["common_codes.group_code", "common_codes.code"],
            name="fk_item_stock_uom",
        ),
        CheckConstraint(f"process_group = '{codes.PROCESS}'", name="ck_item_process_group"),
        CheckConstraint(f"stock_uom_group = '{codes.UOM}'", name="ck_item_stock_uom_group"),
        *code_reference(
            group_column="material_group_group",
            code_column="material_group",
            group_code=codes.MATERIAL_GROUP,
            name="item_material_group",
        ),
        # **양방향이다.** 원자재인데 자재군이 없으면 수입 기준을 끌어올 수 없고,
        # 원자재가 아닌데 자재군이 있으면 만들어져 나온 것에 「무슨 자재인가」가
        # 적힌 것이다. 한쪽만 걸면 다른 쪽으로 새는 줄이 선다.
        CheckConstraint(
            f"(item_type = '{codes.RAW_MATERIAL}') = (material_group IS NOT NULL)",
            name="ck_item_material_group_matches_type",
        ),
        # `uq_item_id_type` 과 **같은 이유로** 둔다 — `id` 가 이미 기본키라 행을
        # 좁히지 않지만, 복합 외래키의 상대가 되려면 그 쌍이 유일키여야 한다.
        #
        # 가리키는 쪽은 검사 기록이다. 검사가 자기 품목의 자재군을 들고 있어야
        # **측정 줄이 그 무리의 기준만 가리키게** 묶을 수 있고, 그 묶음이 없으면
        # 분말을 받은 검사에 점도 기준이 붙는다 — 자재군 축이 닫은 자리가 한 겹
        # 아래에서 다시 열린다.
        UniqueConstraint("id", "material_group", name="uq_item_id_material_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    item_type: Mapped[str] = mapped_column(String(20), index=True)

    # 검사 기준을 끌어오는 라벨. 접두가 아니라 명시적인 열이어야 공정이 바뀔 때
    # 품목 코드를 바꾸지 않는다.
    process: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 위 복합 외래키의 왼쪽 절반. 데이터가 아니라 **구조**이므로 값은 언제나
    # `PROCESS` 이고 CHECK 가 그것을 못박는다.
    process_group: Mapped[str] = mapped_column(
        String(20), default=codes.PROCESS, server_default=codes.PROCESS
    )

    # 재고 단위. **모든 수량이 이 단위로 저장된다** — 잔량을 수불의 합으로
    # 내린 이상 합할 수 있으려면 단위가 하나여야 하기 때문이다.
    #
    # **바꾸면 지나간 수량의 뜻이 바뀐다.** 어느 표에도 단위 사본이 없으므로
    # `EA` 를 `m2` 로 고치는 순간 이미 쌓인 500개가 조용히 「500 m²」가 된다.
    # 지금은 품목을 고치는 경로가 없어 열리지 않는 구멍이고, 품목 수정 화면이
    # 서는 단계에서 정한다 — 그때의 답은 아마 **「단위 변경은 수정이 아니라
    # 새 품목」** 이다. 여기 적어 두는 것은 그 결정을 미룬다는 사실 자체를
    # 코드가 알고 있게 하기 위해서다.

    # 자재군 — **수입 검사 기준이 걸리는 축**이다. 없으면 「수입」 기준 여덟이
    # 원자재 열다섯 전부에 똑같이 걸려, 분말에 점도를 재라고 내밀게 된다.
    #
    # **원자재만 갖는다.** 반제품과 완제품은 만들어져 나온 것이라 「무슨
    # 자재인가」를 물을 수 없다. 위의 양방향 CHECK 가 그것을 못박는다.
    material_group: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 복합 외래키의 왼쪽 절반. 이름이 겹쳐 보이지만 `process`/`process_group` 과
    # 같은 꼴이다 — 칸 이름 뒤에 `_group` 을 붙인 것이 구조를 말하는 자리다.
    material_group_group: Mapped[str] = mapped_column(
        String(20), default=codes.MATERIAL_GROUP, server_default=codes.MATERIAL_GROUP
    )

    stock_uom: Mapped[str] = mapped_column(String(30))
    stock_uom_group: Mapped[str] = mapped_column(
        String(20), default=codes.UOM, server_default=codes.UOM
    )

    # 초기 · 양산. 게이트와 지표가 다르다 (Ppk 1.67 / Cpk 1.33).
    phase: Mapped[str] = mapped_column(
        String(10), default=codes.PHASE_INITIAL, server_default=codes.PHASE_INITIAL
    )

    # 사내가 정한 유효기간 설정기간(일). 로트의 유효기간은 이 값에서 파생된다.
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_stock: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 리드타임은 품목의 값이 아니라 오더마다 다른 **계산 결과**다. 품목이 갖는
    # 것은 계수 둘이고, 소요 시간 = 준비시간 + 개당 시간 × 수량이다. 상수로
    # 두면 100개와 1000개가 같은 시각에 착수한다.
    setup_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    hours_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)

    components: Mapped[list["BomComponent"]] = relationship(
        back_populates="parent_item",
        foreign_keys="[BomComponent.parent_item_id, BomComponent.parent_item_type]",
    )
    used_in: Mapped[list["BomComponent"]] = relationship(
        back_populates="child_item",
        foreign_keys="[BomComponent.child_item_id, BomComponent.child_item_type]",
    )


class BomComponent(Base):
    """2단 고정 BOM 한 줄 — 상위품목이 하위품목을 얼마나 쓰는가.

    **단계가 양쪽의 유형을 정한다.** 1단은 완제품 ← 반제품, 2단은 반제품 ←
    원자재이며, 그것을 복합 외래키와 CHECK 가 함께 강제한다. 그래서 전개가 두
    번으로 못 박히고 재귀가 구조적으로 불가능하다 — 계산이 단순하고 테스트할
    경우의 수가 유한하다.

    유형 두 칸은 파생값이 아니다. 복합 외래키의 절반이며, 품목의 유형과 다를
    수 없다는 것을 데이터베이스가 보증한다.
    """

    __tablename__ = "bom_components"
    __table_args__ = (
        UniqueConstraint(
            "parent_item_id", "child_item_id", name="uq_bom_component_parent_child"
        ),
        CheckConstraint(_BOM_LEVEL_MATCHES_TYPES, name="ck_bom_component_level_types"),
        CheckConstraint("parent_item_id <> child_item_id", name="ck_bom_component_not_self"),
        # 수량은 음수가 될 수 없다. 음수가 섞이면 서로 다른 줄이 0 으로 상쇄되어
        # 합계를 읽는 쪽이 **혼재를 빈 것으로** 읽는다.
        # **0 은 BOM 줄이 아니다.** 하나도 쓰지 않는 자재를 자재표에 적은 것이고,
        # 그 줄은 「이 자재는 어딘가에 쓰인다」는 판단만 통과시킨 뒤 소요량 전개에서
        # 0 을 내놓는다 — 아무 데도 안 쓰이는 자재가 **쓰이는 것처럼 보인다.**
        CheckConstraint(
            f"unit_quantity > 0 AND {is_finite('unit_quantity')}",
            name="ck_bom_component_quantity",
        ),
        ForeignKeyConstraint(
            ["parent_item_id", "parent_item_type"],
            ["items.id", "items.item_type"],
            name="fk_bom_component_parent",
        ),
        ForeignKeyConstraint(
            ["child_item_id", "child_item_type"],
            ["items.id", "items.item_type"],
            name="fk_bom_component_child",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 복합 외래키로만 가리킨다 — 컬럼에도 걸면 같은 관계가 두 번 생긴다.
    parent_item_id: Mapped[int] = mapped_column()
    parent_item_type: Mapped[str] = mapped_column(String(20))
    child_item_id: Mapped[int] = mapped_column()
    child_item_type: Mapped[str] = mapped_column(String(20))
    level: Mapped[int] = mapped_column(Integer)
    unit_quantity: Mapped[float] = mapped_column(Float)

    parent_item: Mapped[Item] = relationship(
        back_populates="components", foreign_keys=[parent_item_id, parent_item_type]
    )
    child_item: Mapped[Item] = relationship(
        back_populates="used_in", foreign_keys=[child_item_id, child_item_type]
    )


class Partner(Base):
    """거래처 — 공급사와 고객사.

    한 표에 둔다. **거래처라는 사실이 하나**이기 때문이다. 유형은 그 거래처가
    어느 흐름에 서는가를 말한다 — 공급사는 발주와 반품에, 고객사는 수주와
    출하에 선다.

    **한 거래처는 역할 하나를 갖는다.** 같은 회사가 양쪽이면 코드를 달리해 두
    줄로 둔다. 역할을 여러 개 갖게 하려면 관계 표가 하나 더 필요한데, 그것이
    필요해지는 자리(같은 회사에 팔면서 사는 거래)가 이 설계에 아직 없다 —
    생기는 날 바꾼다.
    """

    __tablename__ = "partners"
    __table_args__ = (
        CheckConstraint(
            f"partner_type IN ({_quoted(codes.PARTNER_TYPES)})", name="ck_partner_type"
        ),
        CheckConstraint(is_present("code"), name="ck_partner_code_is_present"),
        CheckConstraint(is_present("name"), name="ck_partner_name_is_present"),
        # 품목과 같은 이유다 — 「이 줄의 거래처는 공급사여야 한다」를 거는 쪽이
        # `(id, 유형)` 쌍을 가리킬 수 있어야 한다.
        UniqueConstraint("id", "partner_type", name="uq_partner_id_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    partner_type: Mapped[str] = mapped_column(String(10), index=True)
    # 거래가 끝난 거래처도 지우지 않는다 — 과거 발주와 출하가 이것을 가리킨다.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    supplied_items: Mapped[list["SupplierItem"]] = relationship(back_populates="partner")


class SupplierItem(Base):
    """공급사별 품목 — 구매 리드타임과 단위 환산.

    **단위를 바꾸는 경계는 여기 하나뿐이다.** 구매 단위로 발주하고 재고 단위로
    저장한다. 경계가 둘이면 어느 쪽이 진실인지 알 수 없어지고, 원장의 합이
    성립하지 않는다.

    리드타임이 시간인 것은 생산 리드타임과 단위를 맞추기 위해서다 — 역산이
    두 겹을 같은 자로 재야 「지금 발주해야 늦지 않는다」를 말할 수 있다.
    """

    __tablename__ = "supplier_items"
    __table_args__ = (
        # 공급사여야 한다. 고객사에게 발주할 수는 없다.
        ForeignKeyConstraint(
            ["partner_id", "partner_type"],
            ["partners.id", "partners.partner_type"],
            name="fk_supplier_item_partner",
        ),
        CheckConstraint(
            f"partner_type = '{codes.SUPPLIER}'", name="ck_supplier_item_is_supplier"
        ),
        # **공급사에게 사는 것은 원자재뿐이다.** 반제품과 완제품은 우리가 만든다
        # — 로트가 그것을 이미 강제한다(공급사 출처 로트는 원자재여야 한다).
        # 여기를 열어 두면 **받을 수 없는 구매 마스터**가 선다: 발주는 되는데
        # 입고에서 로트를 만들 수 없는 품목이다.
        ForeignKeyConstraint(
            ["item_id", "item_type"],
            ["items.id", "items.item_type"],
            name="fk_supplier_item_item",
        ),
        CheckConstraint(
            f"item_type = '{codes.RAW_MATERIAL}'", name="ck_supplier_item_is_raw_material"
        ),
        *code_reference(
            group_column="purchase_uom_group",
            code_column="purchase_uom",
            group_code=codes.UOM,
            name="supplier_item_uom",
        ),
        # 환산 계수가 0 이거나 음수면 발주 수량이 재고 수량으로 바뀌지 않는다 —
        # 0 이면 아무리 발주해도 0 이 들어오고, 음수면 재고가 줄어든다.
        CheckConstraint(
            f"conversion_factor > 0 AND {is_finite('conversion_factor')}",
            name="ck_supplier_item_conversion",
        ),
        CheckConstraint(
            f"lead_time_hours >= 0 AND {is_finite('lead_time_hours')}",
            name="ck_supplier_item_lead_time",
        ),
    )

    partner_id: Mapped[int] = mapped_column(primary_key=True)
    partner_type: Mapped[str] = mapped_column(
        String(10), default=codes.SUPPLIER, server_default=codes.SUPPLIER
    )
    # 복합 외래키로만 가리킨다 — 컬럼에도 걸면 같은 관계가 두 번 생긴다.
    item_id: Mapped[int] = mapped_column(primary_key=True)
    item_type: Mapped[str] = mapped_column(
        String(20), default=codes.RAW_MATERIAL, server_default=codes.RAW_MATERIAL
    )

    lead_time_hours: Mapped[float] = mapped_column(Float)
    purchase_uom: Mapped[str] = mapped_column(String(30))
    purchase_uom_group: Mapped[str] = mapped_column(
        String(20), default=codes.UOM, server_default=codes.UOM
    )
    # 구매 단위 하나가 재고 단위로 몇인가. 같은 단위면 1 이다.
    conversion_factor: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")

    partner: Mapped[Partner] = relationship(back_populates="supplied_items")
    item: Mapped[Item] = relationship(foreign_keys=[item_id, item_type])
