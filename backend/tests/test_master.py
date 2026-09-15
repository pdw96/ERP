"""품목 한 표와 2단 BOM — 조각 2."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.master import BomComponent, Item
from tests.factories import add_code, make_bom, make_item, prepare_item_codes


@pytest.fixture
def prepared(session: Session) -> Session:
    """품목이 가리키는 공통코드가 준비된 세션."""
    prepare_item_codes(session)
    return session


# ── 통합이 실제로 자리를 내주는가 ───────────────────────────────────────────


def test_a_semi_finished_item_finally_has_a_seat(prepared: Session) -> None:
    """**표가 둘이던 때는 이 줄이 설 수 없었다.**

    반제품은 만들어지면서 쓰이므로 제품 표에도 자재 표에도 온전히 속하지
    못했다. 한 표가 되면서 2단 BOM 이 실제로 두 단으로 선다.
    """
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA", shelf_life_days=180)
    semi = make_item(codes.SEMI_FINISHED, stock_uom="KG")
    raw = make_item(codes.RAW_MATERIAL, stock_uom="KG")
    prepared.add_all([finished, semi, raw])
    prepared.flush()

    prepared.add(make_bom(finished, semi, level=1))
    prepared.add(make_bom(semi, raw, level=2))
    prepared.flush()

    rows = prepared.query(BomComponent).order_by(BomComponent.level).all()
    assert [row.level for row in rows] == [1, 2]
    assert rows[0].parent_item.item_type == codes.FINISHED_GOODS
    assert rows[0].child_item.item_type == codes.SEMI_FINISHED
    assert rows[1].child_item.item_type == codes.RAW_MATERIAL


@pytest.mark.parametrize("level", codes.BOM_LEVELS)
def test_the_expansion_stops_after_two_levels(prepared: Session, level: int) -> None:
    """3단은 **적을 수가 없다** — 단계가 양쪽 유형을 정하기 때문이다.

    재귀를 막는 것이 규칙이 아니라 구조다. 원자재를 상위로 둔 줄은 어느
    단계로도 설 수 없다.

    단계마다 **세션을 새로 받는다.** 한 테스트 안에서 돌리면 첫 실패 뒤의
    롤백이 품목 삽입까지 되돌려, 다음 단계가 「단계 제약」이 아니라 「없는
    품목」 때문에 실패할 수 있다 — 지금은 CHECK 가 외래키보다 먼저 평가되어
    우연히 맞는 이유로 걸리지만, 그 우연에 기대지 않는다.
    """
    semi = make_item(codes.SEMI_FINISHED, stock_uom="KG")
    raw = make_item(codes.RAW_MATERIAL, code="RM-01", stock_uom="KG")
    other_raw = make_item(codes.RAW_MATERIAL, code="RM-02", stock_uom="KG")
    prepared.add_all([semi, raw, other_raw])
    prepared.flush()

    prepared.add(make_bom(raw, other_raw, level=level))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_level_cannot_pair_the_wrong_types(prepared: Session) -> None:
    """1단에 원자재를 하위로 넣으면 거부된다 — 반제품을 건너뛸 수 없다."""
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA")
    raw = make_item(codes.RAW_MATERIAL, stock_uom="KG")
    prepared.add_all([finished, raw])
    prepared.flush()

    prepared.add(make_bom(finished, raw, level=1))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_bom_line_cannot_declare_a_type_the_item_does_not_have(
    prepared: Session,
) -> None:
    """유형 칸은 파생이 아니라 **복합 외래키의 절반**이다.

    품목의 유형과 다른 값을 적으면 가리킬 품목이 없어 거부된다 — 그래서 두
    곳에 같은 사실이 있어도 갈릴 수 없다.
    """
    finished = make_item(codes.FINISHED_GOODS, stock_uom="EA")
    semi = make_item(codes.SEMI_FINISHED, stock_uom="KG")
    prepared.add_all([finished, semi])
    prepared.flush()

    line = make_bom(finished, semi, level=1)
    line.child_item_type = codes.RAW_MATERIAL  # 실제로는 반제품이다
    prepared.add(line)

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_an_item_cannot_use_itself(prepared: Session) -> None:
    """자기를 하위로 두는 줄은 없다."""
    semi = make_item(codes.SEMI_FINISHED, stock_uom="KG")
    prepared.add(semi)
    prepared.flush()

    prepared.add(make_bom(semi, semi, level=2))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_bom_quantity_cannot_be_negative(prepared: Session) -> None:
    """음수가 섞이면 합계를 읽는 쪽이 혼재를 빈 것으로 읽는다."""
    semi = make_item(codes.SEMI_FINISHED, stock_uom="KG")
    raw = make_item(codes.RAW_MATERIAL, stock_uom="KG")
    prepared.add_all([semi, raw])
    prepared.flush()

    prepared.add(make_bom(semi, raw, level=2, unit_quantity=-1.0))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 유형과 접두 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("item_type", "wrong_code"),
    [
        (codes.FINISHED_GOODS, "RM-01"),
        (codes.SEMI_FINISHED, "FG-01"),
        (codes.RAW_MATERIAL, "SF-01"),
    ],
)
def test_the_prefix_must_match_the_type(
    prepared: Session, item_type: str, wrong_code: str
) -> None:
    """접두는 유형과 유일성만 맡는다 — 그리고 유형과 어긋날 수 없다."""
    prepared.add(make_item(item_type, code=wrong_code))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_an_unknown_item_type_is_refused(prepared: Session) -> None:
    """값이 고정된 그룹이다 — 프로그램이 유형마다 다른 일을 한다."""
    item = make_item(codes.RAW_MATERIAL)
    item.item_type = "부자재"
    prepared.add(item)

    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 유형에 따라 비는 칸 ─────────────────────────────────────────────────────


def test_a_semi_finished_item_has_no_shelf_life(prepared: Session) -> None:
    """「반제품은 유효기간을 두지 않고 제품만 유효기간을 정한다.」

    표가 하나여서 이 규칙을 제약으로 적을 수 있게 됐다.
    """
    prepared.add(make_item(codes.SEMI_FINISHED, stock_uom="KG", shelf_life_days=30))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_raw_material_must_have_a_safety_stock(prepared: Session) -> None:
    """자재 리스크가 이 값을 재고와 곧바로 견준다 — 비면 비교가 성립하지 않는다."""
    prepared.add(make_item(codes.RAW_MATERIAL, safety_stock=None))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_finished_item_may_leave_its_safety_stock_empty(prepared: Session) -> None:
    """값을 정한 사람이 없으면 비어 있는 것이 맞다 — **지어내지 않는다.**"""
    prepared.add(make_item(codes.FINISHED_GOODS, stock_uom="EA", safety_stock=None))

    prepared.flush()  # 터지지 않는 것이 확인이다


def test_lead_time_coefficients_cannot_run_time_backwards(prepared: Session) -> None:
    """음수면 소요 시간이 음수가 되고 착수가 완료보다 뒤에 잡힌다."""
    prepared.add(make_item(codes.SEMI_FINISHED, stock_uom="KG", setup_hours=-1.0))

    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 가변 그룹이 실제로 가변인가 ─────────────────────────────────────────────


def test_a_new_process_code_can_be_used_without_touching_python(
    prepared: Session,
) -> None:
    """공정은 값이 늘 수 있는 그룹이다.

    허용값을 파이썬 상수에서 구워 CHECK 로 박으면 「늘 수 있다」는 선언이
    거짓이 된다 — 운영자가 코드를 더해도 그것을 쓰는 품목이 거부되기 때문이다.
    복합 외래키라야 이 테스트가 통과한다.
    """
    add_code(prepared, codes.PROCESS, "적층경화")
    prepared.flush()

    prepared.add(make_item(codes.SEMI_FINISHED, stock_uom="KG", process="적층경화"))
    prepared.flush()

    item = prepared.query(Item).filter_by(item_type=codes.SEMI_FINISHED).one()
    assert item.process == "적층경화"


def test_an_unknown_process_is_refused(prepared: Session) -> None:
    """없는 공정을 가리키면 검사 기준을 끌어올 곳이 없다."""
    prepared.add(make_item(codes.RAW_MATERIAL, process="존재하지않는공정"))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_an_unknown_stock_unit_is_refused(prepared: Session) -> None:
    """단위가 붙지 않은 수량은 합할 수 없다 — 원장의 합이 성립하지 않는다."""
    prepared.add(make_item(codes.RAW_MATERIAL, stock_uom="되"))

    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_process_is_optional(prepared: Session) -> None:
    """공정이 아직 정해지지 않은 품목도 등록된다 — 복합 키의 한쪽이 NULL 이면
    외래키가 검사하지 않는다."""
    prepared.add(make_item(codes.RAW_MATERIAL, process=None))

    prepared.flush()
