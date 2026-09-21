"""재고 — 로트 한 표.

**설계도와 갈라지는 자리다.** 42판은 자재 로트와 완제품 로트를 두 표로
두었는데, 그것은 통합할 수 없던 기존 구조를 물려받은 결과였다. 품목을 한 표로
묶은 논리가 로트에도 그대로 적용된다 — 반제품 로트는 두 표 어느 쪽에도 앉을
자리가 없다.

원칙 ① — **재고 로트는 언제나 합격 후에 생긴다.** 그래서 「검사 대기」나
「불합격」 같은 상태 칸이 없다: 로트가 있다는 것 자체가 합격했다는 뜻이고,
불합격품은 로트가 되지 않으므로 담을 창고도 필요 없다. 번호의 출처만 다르다.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
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
        # ── 자기를 만든 검사 ────────────────────────────────────────────────
        # **특채 표식을 칸으로 두지 않는 이유가 이것이다.** 로트가 자기를 만든
        # 검사를 가리키면 특채 여부도 판정자도 측정값도 **검사 쪽에 한 번만**
        # 산다. 칸을 따로 두면 같은 사실이 두 곳에 살고, 두 벌은 갈린다.
        #
        # **판정을 함께 가리킨다.** 「불합격이 로트를 만들지 못한다」는 다른 표의
        # 칸을 보는 조건이라 CHECK 로 적을 수 없다 — 판정을 이 줄에 들고 쌍으로
        # 가리키면 아래 CHECK 가 그 줄만 보고 막는다. 특채 플래그를 검사 기록에
        # 건 것과 같은 방식이고, 칸은 외래키에 묶여 **갈릴 수 없다.**
        ForeignKeyConstraint(
            ["inspection_id", "inspection_result"],
            ["inspections.id", "inspections.result"],
            name="fk_lot_inspection",
        ),
        CheckConstraint(
            "(inspection_id IS NULL) = (inspection_result IS NULL)",
            name="ck_lot_inspection_result_matches_inspection",
        ),
        # **원칙 ① 이 제약이 되는 자리다.** 불합격은 재고가 되지 않는다.
        CheckConstraint(
            f"inspection_result IS DISTINCT FROM '{codes.JUDGMENT_FAILED}'",
            name="ck_lot_is_not_from_a_failed_inspection",
        ),
        # **「사 온 로트에는 검사가 있다」를 걸지 않는다.** 걸어 봤더니 기초재고가
        # 막혔다 — 과거를 소급하지 않기로 했으므로 이월로 깔리는 자재 로트에는
        # 적을 검사도 합격일도 없고, 그것은 이미 선 사실이다
        # (`tests/test_inventory.py` 의 「기초재고」 둘).
        #
        # 그래서 검사를 **가리키는** 로트만 판정에 묶인다. 「검사 없이 선 자재
        # 로트」와 「이월로 깔린 자재 로트」를 데이터베이스가 가르려면 이월을
        # 표시할 자리가 있어야 하고, 그 자리는 전기이월이 서는 조각의 것이다.
        # **한 판정은 로트를 한 번만 만든다.** 판정이 검사 한 건에 하나이므로
        # 둘이 서면 같은 합격으로 재고가 두 벌 생긴다.
        UniqueConstraint("inspection_id", name="uq_lot_inspection"),
        # `id` 가 이미 기본키라 행을 좁히지 않는다 — **원장 줄이 가리킬 상대**다.
        # 원장의 입고 줄이 「그 로트를 만든 검사」를 가리키는지는 이 쌍이 없으면
        # 데이터베이스가 보증하지 못한다.
        UniqueConstraint("id", "inspection_id", name="uq_lot_id_inspection"),
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

    # **특채 표식은 이 칸을 통해 검사 쪽에 있다.** 로트에 「특채인가」를 따로 두지
    # 않는다 — 같은 사실이 두 곳에 살면 갈린다.
    inspection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # **값을 나르는 칸이 아니라 구조다.** 위의 외래키가 검사의 판정에 묶으므로
    # 여기 담기는 것은 「이 로트를 만든 판정이 무엇이었는가」 하나뿐이고, 검사
    # 쪽 판정이 바뀌면 이 줄이 가리키던 짝이 사라져 그 수정 자체가 막힌다 —
    # 원칙 ⑦ 이 여기서도 한 겹 선다.
    inspection_result: Mapped[str | None] = mapped_column(String(10), nullable=True)

    item: Mapped[Item] = relationship(foreign_keys=[item_id, item_type])


class StockLedgerEntry(Base):
    """수불 원장 한 줄 — **로트가 생기고 움직인 사실.**

    **원칙 ⑦이 이 표의 모양을 정한다 — 일어난 일은 지우지 않는다.** 줄을 지우거나
    고치지 않고, 취소는 **반대 방향의 새 줄**이다. 그래서 삭제 칸도 수정 시각도
    없다: 있으면 지우는 길이 생기고, 길이 있으면 언젠가 지나간다.

    ### 수량은 늘 양수다 — 방향은 유형이 말한다

    `txn_type_attributes.total_effect` 가 증가 · 감소 · 불변 · 기준점 · 양방향을
    **이미 들고 있다.** 원장 줄에 부호를 또 두면 같은 사실이 두 곳에 살고, 유형은
    「감소」인데 수량이 양수인 줄을 제약이 막지 못한다.

    부호를 쓰면 `>= 0` 을 걸 수 없다는 것도 값이다. 하한이 없는 칸은
    `is_finite()` 단독이 되고, 그것은 `NaN` 은 막아도 **음수 입고**는 막지 않는다.

    ### 유형은 공통코드가 아니라 **속성 줄**을 가리킨다

    공통코드를 가리키면 「그 코드가 있다」까지만 증명된다 — 총량 영향도 근거
    문서도 없는 유형이 원장에 서고, 그러면 잔량을 세는 쪽이 **그 줄을 더해야
    하는지 빼야 하는지 모른다.** 속성 줄을 가리키면 그 한 겹이 더 막힌다.

    ### 이 조각의 원장에 나는 줄은 구매입고 하나다

    합격이 로트를 만들고 그 자리에 입고 한 줄이 남는다. 나머지 열한 유형은 내는
    쪽이 3~8단계에 있으므로, 받아 두면 **근거 문서가 없는 줄**이 서고 화면에서는
    실제로 일어난 일처럼 보인다. 그 유형을 내는 조각이 설 때 CHECK 가 함께
    넓어진다.

    > **데이터베이스가 아직 보증하지 못하는 것이 하나 있다** — 이 줄이 가리키는
    > 검사가 **그 로트를 만든 검사인가**. 묶으려면 로트가 자기를 만든 검사를
    > 가리켜야 하는데(`lots.inspection_id`), 그 칸은 로트를 실제로 만드는 쪽이
    > 서는 조각에서 붙는다. 지금은 붙일 수 있어도 **채우는 쪽이 없다.**
    """

    __tablename__ = "stock_ledger_entries"
    __table_args__ = (
        # **그 로트를 만든 검사여야 한다.** `lot_id` 와 `inspection_id` 를 따로
        # 가리키면 둘 다 실재한다는 것까지만 증명된다 — 남의 검사를 가리키는
        # 입고 줄이 서고, 그러면 「왜 이 물건이 들어왔는가」로 내려가는 길이
        # 엉뚱한 판정에 닿는다. 쌍으로 가리키면 그 한 겹이 더 막힌다.
        ForeignKeyConstraint(
            ["lot_id", "inspection_id"],
            ["lots.id", "lots.inspection_id"],
            name="fk_stock_ledger_entry_lot",
        ),
        # **속성 줄을 가리킨다.** 공통코드를 가리키면 총량 영향이 없는 유형이
        # 원장에 설 수 있고, 그러면 잔량을 세는 쪽이 방향을 알 수 없다.
        ForeignKeyConstraint(
            ["txn_type_group", "txn_type"],
            ["txn_type_attributes.group_code", "txn_type_attributes.code"],
            name="fk_stock_ledger_entry_txn_type",
        ),
        CheckConstraint(
            f"txn_type_group = '{codes.TXN_TYPE}'", name="ck_stock_ledger_entry_txn_type_group"
        ),
        # 이 조각이 내는 유형은 하나다. 넓히는 것은 마이그레이션이다.
        CheckConstraint(
            f"txn_type = '{codes.TXN_PURCHASE_RECEIPT}'",
            name="ck_stock_ledger_entry_is_a_purchase_receipt",
        ),
        # `NaN >= 0` 이 참이라 하한만으로는 막지 못한다. 한 줄이 들어오면 이후의
        # **모든 잔량 합계가 `NaN`** 이 되고 비교가 전부 거짓이라 재고가 조용히
        # 사라진다 — 원장은 합으로 읽는 표이므로 그 피해가 표 하나에 그치지 않는다.
        CheckConstraint(
            f"quantity >= 0 AND {is_finite('quantity')}", name="ck_stock_ledger_entry_quantity"
        ),
        # **로트 하나에 입고 줄은 하나다.** 둘이 서면 같은 물건이 두 번 들어온
        # 것이 되고, 잔량이 실물의 두 배가 된다.
        #
        # 유형을 조건에 적어 **부분 유일 인덱스**로 둔다. 그냥 `UNIQUE (lot_id)`
        # 로 두면 오늘은 같은 뜻이지만, 불출이 서는 날 한 로트에 여러 줄이 나야
        # 하므로 그때 이 제약을 손봐야 한다 — 손봐야 하는 제약은 손보지 않은
        # 채로 남는다.
        Index(
            "uq_stock_ledger_entry_one_receipt_per_lot",
            "lot_id",
            unique=True,
            postgresql_where=text(f"txn_type = '{codes.TXN_PURCHASE_RECEIPT}'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    lot_id: Mapped[int] = mapped_column(Integer)

    txn_type: Mapped[str] = mapped_column(String(30))
    txn_type_group: Mapped[str] = mapped_column(
        String(20), default=codes.TXN_TYPE, server_default=codes.TXN_TYPE
    )

    quantity: Mapped[float] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)

    # **입고 줄은 자기를 만든 검사를 가리킨다.** 이 조각의 줄은 전부 판정에서
    # 나오므로 비어 있을 수 없다 — 비워 두면 근거 없는 입고가 선다. 판정에서
    # 나지 않는 줄(전기이월 · 생산입고)이 서는 날 함께 넓어진다.
    inspection_id: Mapped[int] = mapped_column(Integer)
