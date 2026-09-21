"""재고 로트 한 표 — 조각 6."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.inventory import Lot
from app.db.master import Item
from tests.factories import make_item, prepare_item_codes


def _lot(item: Item, **overrides: object) -> Lot:
    """제약을 통과하는 로트 하나. 유형에 맞는 기본값이 붙는다."""
    from_supplier = item.item_type == codes.RAW_MATERIAL
    fields: dict[str, object] = {
        "item_id": item.id,
        "item_type": item.item_type,
        "lot_number": "LOT-001",
        "lot_origin": codes.LOT_FROM_SUPPLIER if from_supplier else codes.LOT_FROM_OWN,
        "warehouse": codes.WAREHOUSE_RAW if from_supplier else codes.WAREHOUSE_PRODUCTION,
        "stock_type": codes.STOCK_GOOD,
        "quantity": 100.0,
        "received_date": date(2026, 9, 1) if from_supplier else None,
        "produced_date": None if from_supplier else date(2026, 9, 1),
        "passed_date": date(2026, 9, 2),
    }
    fields.update(overrides)
    return Lot(**fields)


@pytest.fixture
def prepared(session: Session) -> Session:
    prepare_item_codes(session)
    return session


# ── 한 표가 세 유형을 담는가 ────────────────────────────────────────────────


def test_all_three_item_types_share_one_lot_table(prepared: Session) -> None:
    """**42판은 이것을 두 표로 두었다.**

    반제품 로트는 자재 로트에도 완제품 로트에도 앉을 자리가 없었다. 품목을 한
    표로 묶은 논리가 로트에도 그대로 적용된다.
    """
    raw = make_item(codes.RAW_MATERIAL, code="RM-01")
    semi = make_item(codes.SEMI_FINISHED, code="SF-01")
    finished = make_item(codes.FINISHED_GOODS, code="FG-01", stock_uom="EA")
    prepared.add_all([raw, semi, finished])
    prepared.flush()

    prepared.add(_lot(raw, lot_number="SUP-A-001"))
    prepared.add(_lot(semi, lot_number="B-2609-01"))
    prepared.add(_lot(finished, lot_number="B-2609-02", warehouse=codes.WAREHOUSE_FINISHED))
    prepared.flush()

    kinds = {lot.item_type for lot in prepared.query(Lot).all()}
    assert kinds == {codes.RAW_MATERIAL, codes.SEMI_FINISHED, codes.FINISHED_GOODS}


def test_a_lot_has_no_status_column(prepared: Session) -> None:
    """원칙 ① — **로트가 있다는 것 자체가 합격을 뜻한다.**

    「검사 대기」도 「불합격」도 칸이 아니다. 불합격품은 로트가 되지 않으므로
    담을 창고도 상태값도 필요 없다.
    """
    columns = {column.name for column in Lot.__table__.columns}

    assert "qc_status" not in columns
    assert "status" not in columns
    assert "is_passed" not in columns


# ── 로트가 온 곳 ────────────────────────────────────────────────────────────


def test_a_raw_material_lot_comes_from_a_supplier(prepared: Session) -> None:
    """자재는 사 온다 — 자사 배치 번호를 달 수 없다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(
        _lot(
            raw,
            lot_origin=codes.LOT_FROM_OWN,
            received_date=None,
            produced_date=date(2026, 9, 1),
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_an_own_lot_cannot_claim_a_received_date(prepared: Session) -> None:
    """만든 것에는 생산일이 있고 입고일이 없다 — 두 날짜가 섞이면 FIFO 가 흔들린다."""
    semi = make_item(codes.SEMI_FINISHED)
    prepared.add(semi)
    prepared.flush()

    prepared.add(_lot(semi, received_date=date(2026, 9, 1)))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_supplied_lot_needs_a_received_date(prepared: Session) -> None:
    """입고일이 없으면 FIFO 가 순서를 정할 수 없다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, received_date=None))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 창고가 담는 것 ──────────────────────────────────────────────────────────


def test_the_finished_warehouse_holds_only_finished_goods(prepared: Session) -> None:
    """제품창고에 자재가 들어가면 출하 가능 재고가 틀린다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, warehouse=codes.WAREHOUSE_FINISHED))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_production_warehouse_holds_all_three(prepared: Session) -> None:
    """투입 대기 자재 · 반제품 · 완제품이 함께 있다 — 세 갈래가 한 창고에 선다."""
    raw = make_item(codes.RAW_MATERIAL, code="RM-01")
    semi = make_item(codes.SEMI_FINISHED, code="SF-01")
    finished = make_item(codes.FINISHED_GOODS, code="FG-01", stock_uom="EA")
    prepared.add_all([raw, semi, finished])
    prepared.flush()

    prepared.add(_lot(raw, lot_number="A", warehouse=codes.WAREHOUSE_PRODUCTION))
    prepared.add(_lot(semi, lot_number="B", warehouse=codes.WAREHOUSE_PRODUCTION))
    prepared.add(_lot(finished, lot_number="C", warehouse=codes.WAREHOUSE_PRODUCTION))

    prepared.flush()


def test_the_raw_warehouse_holds_only_materials(prepared: Session) -> None:
    """원재료창고에 완제품이 설 자리는 없다."""
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA")
    prepared.add(finished)
    prepared.flush()

    prepared.add(_lot(finished, warehouse=codes.WAREHOUSE_RAW))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 재고구분 — 단방향이다 ───────────────────────────────────────────────────


def test_defective_stock_lives_only_in_the_finished_warehouse(
    prepared: Session,
) -> None:
    """불합격품은 재고가 되지 않으므로 앞의 두 창고에 불량품이 있을 수 없다.

    불량품이 되는 길은 하나뿐이다 — 제품창고에 들어온 뒤 OQC 에서 떨어져
    양불이동되는 것.
    """
    semi = make_item(codes.SEMI_FINISHED)
    prepared.add(semi)
    prepared.flush()

    prepared.add(_lot(semi, stock_type=codes.STOCK_DEFECTIVE))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_finished_warehouse_still_holds_good_stock(prepared: Session) -> None:
    """**반대 방향은 걸지 않는다.**

    설계도 지적 ①이 고치라고 한 자리다. 제품창고 ⟺ 불량품을 양방향으로 묶으면
    제품창고의 정상 재고가 설 수 없다 — 그 창고에 들어오는 조건은 합격이고,
    안에 불량품도 **함께** 있는 것이다.
    """
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA")
    prepared.add(finished)
    prepared.flush()

    prepared.add(
        _lot(
            finished,
            lot_number="GOOD",
            warehouse=codes.WAREHOUSE_FINISHED,
            stock_type=codes.STOCK_GOOD,
        )
    )
    prepared.add(
        _lot(
            finished,
            lot_number="BAD",
            warehouse=codes.WAREHOUSE_FINISHED,
            stock_type=codes.STOCK_DEFECTIVE,
        )
    )
    prepared.flush()

    kinds = {lot.stock_type for lot in prepared.query(Lot).all()}
    assert kinds == {codes.STOCK_GOOD, codes.STOCK_DEFECTIVE}


# ── 재작업과 유효기간 ───────────────────────────────────────────────────────


def test_rework_is_ours_only(prepared: Session) -> None:
    """공급사 물건은 반품하지 재작업하지 않는다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, reworked=True))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_rework_is_read_from_a_column_not_from_the_number(prepared: Session) -> None:
    """번호는 `...R` 로 남되 **판정을 문자열에서 하지 않는다.**

    창고의 라벨과 장부가 같아야 사람이 찾을 수 있으므로 번호는 그대로 두고,
    관리도가 「선은 정상분이 긋는다」를 가를 때 읽는 것은 이 칸이다. 번호를
    잘라 읽으면 우연히 R 로 끝나는 번호를 오판한다.
    """
    semi = make_item(codes.SEMI_FINISHED)
    prepared.add(semi)
    prepared.flush()

    lot = _lot(semi, lot_number="B-2609-01R", reworked=True)
    prepared.add(lot)
    prepared.flush()

    assert lot.reworked is True
    assert lot.lot_number.endswith("R")


def test_rework_is_off_by_default(prepared: Session) -> None:
    """예/아니오다 — 재작업 2회인 로트는 존재할 수 없다."""
    semi = make_item(codes.SEMI_FINISHED)
    prepared.add(semi)
    prepared.flush()

    lot = _lot(semi)
    prepared.add(lot)
    prepared.flush()

    assert lot.reworked is False


def test_a_semi_finished_lot_has_no_expiry(prepared: Session) -> None:
    """「반제품은 유효기간을 두지 않는다」가 로트에서도 지켜진다."""
    semi = make_item(codes.SEMI_FINISHED)
    prepared.add(semi)
    prepared.flush()

    prepared.add(_lot(semi, expiry_date=date(2027, 1, 1)))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_baseline_lot_may_not_know_when_it_passed(prepared: Session) -> None:
    """기초재고에는 적을 합격일이 없다 — 과거를 소급하지 않기 때문이다.

    「합격했는가」는 로트가 있다는 것으로 이미 답해졌고, 비는 것은 **합격한
    날을 모르는** 경우다. 없는 값을 지어내지 않는다.
    """
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, passed_date=None))

    prepared.flush()


# ── 번호의 유일성 ───────────────────────────────────────────────────────────


def test_two_lots_of_one_item_cannot_share_a_number(prepared: Session) -> None:
    """같은 품목에 같은 번호가 둘이면 어느 쪽을 내보낸 것인지 알 수 없다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, lot_number="SUP-A-001"))
    prepared.flush()
    prepared.add(_lot(raw, lot_number="SUP-A-001"))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_two_items_may_share_a_lot_number(prepared: Session) -> None:
    """유일키는 **품목마다** 본다 — 번호를 우리가 짓게 된 뒤에도 그대로 둔다.

    왜 그대로인지는 `docs/schema-2단계.md` 의 「로트 번호는 우리가 짓는다」가
    적는다. 좁히면 오늘 통과하지만 **그 결정을 뒤집는다.**
    """
    first = make_item(codes.RAW_MATERIAL, code="RM-01")
    second = make_item(codes.RAW_MATERIAL, code="RM-02")
    prepared.add_all([first, second])
    prepared.flush()

    prepared.add(_lot(first, lot_number="2026-09-01"))
    prepared.add(_lot(second, lot_number="2026-09-01"))

    prepared.flush()


def test_a_lot_quantity_cannot_be_negative(prepared: Session) -> None:
    """잔량이 음수인 로트는 없다 — 줄어드는 것은 수불 줄이지 로트가 아니다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, quantity=-1.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), float("-inf")])
def test_a_lot_quantity_must_be_a_number_you_can_count(
    prepared: Session, quantity: float
) -> None:
    """**`NaN` 은 `quantity >= 0` 을 통과한다.**

    PostgreSQL 이 정렬에서 `NaN` 을 모든 수보다 크게 두기 때문이다 — 하한만
    걸어 둔 칸은 「음수가 아니다」까지만 보고 **셀 수 없는 값을 받아들인다.**

    들어오고 나면 되돌릴 수 없다. 그 로트 하나가 이후의 모든 합계를 `NaN` 으로
    만들고, `NaN` 과의 비교는 전부 거짓이라 재고 조회에서 **조용히 사라진다.**
    """
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, quantity=quantity))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_lot_cannot_pass_before_it_arrives(prepared: Session) -> None:
    """들어오기 전에 합격할 수 없다.

    이 날짜가 FIFO 와 만료 판정에 그대로 쓰이므로, 거꾸로 선 줄은 터지지 않고
    **조용히 틀린 재고**를 만든다.
    """
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, received_date=date(2026, 9, 10), passed_date=date(2026, 9, 1)))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_lot_that_arrives_and_passes_on_the_same_day_stands(prepared: Session) -> None:
    """**등호가 경계다** — 오늘 들어와 오늘 합격하는 것이 이 업무의 정상 경로다.

    제약은 `passed_date >= received_date` 인데 그 등호를 재는 갈래가 없었다.
    위아래의 갈래는 전부 **엄격한 부등**이고, 등호가 실제로 밟히는 곳은 쓰기
    경로뿐인데 그것은 `RECEIVED` 가 **하필 그날과 같아서** 생긴 우연이었다 —
    날이 바뀌면 그 갈래가 조용히 사라진다. 제약이 사실을 막으면 안 되고,
    막히면 합격이 전부 500 이 된다.
    """
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    same_day = date(2026, 9, 10)
    prepared.add(_lot(raw, received_date=same_day, passed_date=same_day))
    prepared.flush()

    assert prepared.query(Lot).one().passed_date == same_day


def test_a_lot_cannot_expire_before_it_exists(prepared: Session) -> None:
    """생기기 전에 만료될 수 없다."""
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(
        _lot(
            raw,
            received_date=date(2026, 9, 10),
            passed_date=date(2026, 9, 11),
            expiry_date=date(2026, 9, 5),
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_baseline_lot_still_takes_null_dates(prepared: Session) -> None:
    """날짜 순서를 걸어도 **기초재고의 빈 합격일은 그대로 통과한다.**

    제약이 사실을 막으면 안 된다 — 과거를 소급하지 않기로 했으므로 이월로
    깔리는 로트에는 적을 날짜가 없다.
    """
    raw = make_item(codes.RAW_MATERIAL)
    prepared.add(raw)
    prepared.flush()

    prepared.add(_lot(raw, passed_date=None, expiry_date=date(2027, 1, 1)))

    prepared.flush()
