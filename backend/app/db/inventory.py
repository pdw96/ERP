"""재고 — 로트 한 표.

**설계도와 갈라지는 자리다.** 42판은 자재 로트와 완제품 로트를 두 표로
두었는데, 그것은 통합할 수 없던 기존 구조를 물려받은 결과였다. 품목을 한 표로
묶은 논리가 로트에도 그대로 적용된다 — 반제품 로트는 두 표 어느 쪽에도 앉을
자리가 없다.

원칙 ① — **재고 로트는 언제나 합격 후에 생긴다.** 그래서 「검사 대기」나
「불합격」 같은 상태 칸이 없다: 로트가 있다는 것 자체가 합격했다는 뜻이고,
불합격품은 로트가 되지 않으므로 담을 창고도 필요 없다. 번호의 출처만 다르다.
"""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import codes
from app.db.base import Base
from app.db.constraints import is_finite, is_present
from app.db.master import Item


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# 어느 창고가 어느 품목을 담는가.
_WAREHOUSE_HOLDS_ITEM_TYPE = " OR ".join(
    f"(warehouse = '{warehouse}' AND item_type IN ({_quoted(item_types)}))"
    for warehouse, item_types in codes.WAREHOUSE_ITEM_TYPES.items()
)

# 번호의 출처가 품목 유형을 따른다 — 자재는 사 오고 자사 품목은 만들어 낸다.
_ORIGIN_MATCHES_ITEM_TYPE = " OR ".join(
    f"(lot_origin = '{origin}' AND item_type IN ({_quoted(item_types)}))"
    for origin, item_types in codes.LOT_ORIGIN_ITEM_TYPES.items()
)


class Lot(Base):
    """재고 로트 한 줄 — 자재 · 반제품 · 완제품이 한 표에 산다."""

    __tablename__ = "lots"
    __table_args__ = (
        # 같은 품목에 같은 로트 번호가 둘일 수 없다. 번호만으로 전역 유일을
        # 요구하지는 않는다 — **공급사 번호는 우리가 짓지 않으므로** 다른
        # 공급사가 같은 번호를 쓸 수 있다.
        UniqueConstraint("item_id", "lot_number", name="uq_lot_item_number"),
        ForeignKeyConstraint(
            ["item_id", "item_type"],
            ["items.id", "items.item_type"],
            name="fk_lot_item",
        ),
        CheckConstraint(is_present("lot_number"), name="ck_lot_number_is_present"),
        CheckConstraint(f"warehouse IN ({_quoted(codes.WAREHOUSES)})", name="ck_lot_warehouse"),
        CheckConstraint(
            f"stock_type IN ({_quoted(codes.STOCK_TYPES)})", name="ck_lot_stock_type"
        ),
        CheckConstraint(f"lot_origin IN ({_quoted(codes.LOT_ORIGINS)})", name="ck_lot_origin"),
        CheckConstraint(_WAREHOUSE_HOLDS_ITEM_TYPE, name="ck_lot_warehouse_holds_type"),
        CheckConstraint(_ORIGIN_MATCHES_ITEM_TYPE, name="ck_lot_origin_matches_type"),
        CheckConstraint(f"quantity >= 0 AND {is_finite('quantity')}", name="ck_lot_quantity"),
        # **단방향이다.** 불량품은 제품창고에만 있다 — 불합격품은 재고가 되지
        # 않으므로 앞의 두 창고에서 생길 수 없고, OQC 에서 떨어져 양불이동된
        # 것만 불량품이 된다.
        #
        # 반대 방향은 걸지 않는다. 제품창고에 있다고 불량품인 것이 아니며,
        # 양방향으로 묶으면 제품창고의 정상 재고가 설 수 없다.
        CheckConstraint(
            f"stock_type <> '{codes.STOCK_DEFECTIVE}'"
            f" OR warehouse = '{codes.WAREHOUSE_FINISHED}'",
            name="ck_lot_defective_only_in_finished_warehouse",
        ),
        # 사 온 로트에는 입고일이 있고 생산일이 없다.
        CheckConstraint(
            f"lot_origin <> '{codes.LOT_FROM_SUPPLIER}'"
            " OR (received_date IS NOT NULL AND produced_date IS NULL)",
            name="ck_lot_supplied_has_received_date",
        ),
        # 만든 로트에는 생산일이 있고 입고일이 없다.
        CheckConstraint(
            f"lot_origin <> '{codes.LOT_FROM_OWN}'"
            " OR (produced_date IS NOT NULL AND received_date IS NULL)",
            name="ck_lot_produced_has_produced_date",
        ),
        # 재작업은 우리가 만든 것에만 있다 — 공급사 물건은 반품하지 재작업하지
        # 않는다.
        CheckConstraint(
            f"NOT reworked OR lot_origin = '{codes.LOT_FROM_OWN}'",
            name="ck_lot_rework_is_ours",
        ),
        # 「반제품은 유효기간을 두지 않는다」가 로트에서도 지켜진다.
        CheckConstraint(
            f"item_type <> '{codes.SEMI_FINISHED}' OR expiry_date IS NULL",
            name="ck_lot_semi_finished_has_no_expiry",
        ),
        # **날짜가 거꾸로 선 로트는 없다.** 들어오기 전에 합격할 수 없고, 생기기
        # 전에 만료될 수 없다. 이 값들이 FIFO 와 만료 판정에 그대로 쓰이므로,
        # 거꾸로 된 줄은 터지지 않고 **조용히 틀린 재고**를 만든다.
        #
        # 비는 것은 그대로 허용한다 — 기초재고에는 적을 합격일이 없다.
        CheckConstraint(
            "passed_date IS NULL" " OR passed_date >= COALESCE(received_date, produced_date)",
            name="ck_lot_passed_after_arrival",
        ),
        CheckConstraint(
            "expiry_date IS NULL"
            " OR expiry_date >= COALESCE(passed_date, received_date, produced_date)",
            name="ck_lot_expires_after_it_exists",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # 복합 외래키로만 가리킨다. 컬럼에도 외래키를 걸면 같은 관계가 두 번
    # 생기고, 조인할 길이 둘이라 관계를 세울 수 없다.
    item_id: Mapped[int] = mapped_column()
    # 복합 외래키의 절반. 품목의 유형과 다를 수 없다.
    item_type: Mapped[str] = mapped_column(String(20))

    # 자재는 공급사 번호, 자사 품목은 배치 번호. 재작업분은 번호가 `...R` 로
    # 끝나지만 **판정을 문자열에서 하지 않는다** — 그것은 아래 칸이 말한다.
    lot_number: Mapped[str] = mapped_column(String(50), index=True)
    lot_origin: Mapped[str] = mapped_column(String(10))

    warehouse: Mapped[str] = mapped_column(String(20), index=True)
    stock_type: Mapped[str] = mapped_column(
        String(10), default=codes.STOCK_GOOD, server_default=codes.STOCK_GOOD
    )
    quantity: Mapped[float] = mapped_column(Float)

    received_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    produced_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 합격일. 완제품 유효기간의 기산점이다.
    #
    # **비울 수 있게 둔다.** 로트가 있다는 것 자체가 합격을 뜻하므로(원칙 ①)
    # 「합격했는가」는 구조가 이미 답한다. 비는 것은 **합격한 날을 모르는**
    # 경우이고, 기초재고가 정확히 그렇다 — 과거를 소급하지 않기로 했으므로
    # 이월로 깔리는 로트에는 적을 날짜가 없다. 없는 값을 지어내지 않는다.
    passed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 파생해 저장한다. 라벨에 찍혀 나갔으므로 설정기간을 바꿔도 이미 부여된
    # 만료일은 바뀌지 않는다 — 「밖으로 나간 값은 박아 둔다」.
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 예/아니오다. **재작업 2회인 로트는 존재할 수 없다** — 로트는 합격 후에만
    # 생기므로, 재작업분이 재검사에서 또 떨어지면 로트가 아예 만들어지지 않고
    # 폐기된다.
    reworked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # **특채로 들어온 로트에는 아직 표식이 없다.** 원칙 ①의 예외 하나가 특채이고
    # 거기에는 표식이 남아야 하는데, 그것을 담을 자리가 이 표에 없다.
    # `nonconformity_stage_rules.special_acceptance_allowed` 는 **그 사유가 특채를
    # 허용하는가**를 말할 뿐, 이 로트가 실제로 그 길로 들어왔는지는 말하지 않는다.
    #
    # 칸 하나로 둘지, 로트가 **자기를 만든 검사를 가리키게** 해서 구조로 답할지는
    # 검사 표가 서는 2단계에서 정한다. 지금 칸을 두면 2단계가 검사를 가리키게 하는
    # 순간 같은 사실이 두 곳에 살고, 두 벌은 반드시 갈린다.
    #
    # 1단계에 쓰기 경로가 없으므로 아직 틀린 데이터가 들어올 자리는 아니다 —
    # **로트를 만드는 길이 서는 바로 그 단계에서 함께 선다.**

    item: Mapped[Item] = relationship(foreign_keys=[item_id, item_type])
