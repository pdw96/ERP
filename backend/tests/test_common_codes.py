"""공통코드 두 표 — 조각 1.

여기서 확인하는 것은 **그룹 목록이 설계와 맞는가**와 **본체가 무엇을
거부하는가**다. 값(코드 하나하나)은 시드가 넣으므로 `test_seed.py` 가 본다.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.common_codes import CodeGroup, CommonCode


def _group(group_code: str = codes.UOM) -> CodeGroup:
    definition = next(g for g in codes.CODE_GROUPS if g.group_code == group_code)
    return CodeGroup(
        group_code=definition.group_code,
        name=definition.name,
        value_fixed=definition.value_fixed,
        description=definition.description,
    )


# ── 그룹 목록 ───────────────────────────────────────────────────────────────


def test_there_are_twenty_four_groups() -> None:
    """그룹 스물넷 — 값 고정 열다섯 · 값 가변 아홉.

    자재군이 아홉째 가변 그룹이다. 프로그램은 자재군을 보고 분기하지 않고
    기준을 찾는 주소로만 쓰므로, 무리가 늘어도 고장 나는 코드가 없다.
    """
    fixed = [g for g in codes.CODE_GROUPS if g.value_fixed]
    growable = [g for g in codes.CODE_GROUPS if not g.value_fixed]

    assert len(codes.CODE_GROUPS) == 24
    assert len(fixed) == 15
    assert len(growable) == 9


def test_group_codes_are_unique() -> None:
    """이름으로 부르는 목록이라 겹치면 어느 쪽을 부른 것인지 알 수 없다."""
    assert len(set(codes.GROUP_CODES)) == len(codes.GROUP_CODES)


def test_every_group_says_why_it_is_fixed_or_growable() -> None:
    """설명이 비어 있으면 「왜 못 늘리는가」를 아무도 모른 채 규칙만 남는다."""
    for group in codes.CODE_GROUPS:
        assert group.name.strip(), f"{group.group_code} 에 명칭이 없다"
        assert group.description.strip(), f"{group.group_code} 에 설명이 없다"


def test_the_groups_that_branch_are_the_fixed_ones() -> None:
    """가르는 잣대는 하나 — 프로그램이 그 값을 보고 분기하는가.

    분기하는 그룹의 값을 화면에서 늘리면 그것을 처리할 코드가 없다. 목록이
    흔들리면 그 구조가 무너지므로 여기에 못 박는다.
    """
    fixed = {g.group_code for g in codes.CODE_GROUPS if g.value_fixed}

    assert fixed == {
        codes.WAREHOUSE,
        codes.STOCK_TYPE,
        codes.ITEM_TYPE,
        codes.TXN_TYPE,
        codes.INSP_STAGE,
        codes.ORDER_TYPE,
        codes.ORDER_MODE,
        codes.SHIP_TYPE,
        codes.ITEM_PHASE,
        codes.MEAS_KIND,
        codes.SIGMA_SRC,
        codes.WE_RULE,
        codes.SHIFT,
        codes.SETTLE_TYPE,
        codes.RISK_STATUS,
    }


def test_order_type_and_order_mode_are_two_axes_not_one() -> None:
    """한 칸에 두 축을 담으면 그 조합을 적을 수 없다.

    시양산 **반제품** 오더는 있을 수 있는 것이다 — 2단 BOM 이라 시양산도 두
    오더로 전개된다. 「제품 · 반제품 · 시양산」을 한 그룹에 담으면 그 줄이
    설 자리가 없다.
    """
    assert codes.ORDER_TYPE in codes.GROUP_CODES
    assert codes.ORDER_MODE in codes.GROUP_CODES


# ── 본체가 거부하는 것 ──────────────────────────────────────────────────────


def test_a_code_belongs_to_a_group_that_exists(session: Session) -> None:
    """없는 그룹의 코드는 들어가지 않는다 — 분류가 없는 분류값은 뜻이 없다."""
    session.add(CommonCode(group_code="NOT_A_GROUP", code="X", name="x"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_the_same_code_cannot_be_registered_twice_in_a_group(session: Session) -> None:
    """코드값은 주소다 — 한 그룹에 같은 주소가 둘이면 가리킬 곳이 갈린다."""
    session.add(_group())
    session.add(CommonCode(group_code=codes.UOM, code="EA", name="개"))
    session.flush()

    session.add(CommonCode(group_code=codes.UOM, code="EA", name="낱개"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_the_same_code_may_live_in_two_different_groups(session: Session) -> None:
    """그룹이 다르면 같은 글자여도 다른 주소다 — 키가 (그룹, 코드)인 이유다."""
    session.add(_group(codes.UOM))
    session.add(_group(codes.DEPT))
    session.add(CommonCode(group_code=codes.UOM, code="EA", name="개"))
    session.add(CommonCode(group_code=codes.DEPT, code="EA", name="설비팀"))

    session.flush()  # 터지지 않는 것이 확인이다


@pytest.mark.parametrize("blank", ["", " ", "\t", "　"])
def test_a_code_value_cannot_be_blank(session: Session, blank: str) -> None:
    """주소가 비면 그 줄을 가리키는 모든 기록이 갈 곳을 잃는다.

    전각 공백(`　`)까지 보는 것은 한국어 입력에서 실제로 섞여 들어오기
    때문이다 — 눈으로는 빈 칸과 구별되지 않는다.
    """
    session.add(_group())
    session.add(CommonCode(group_code=codes.UOM, code=blank, name="이름"))

    with pytest.raises(IntegrityError):
        session.flush()


def test_a_code_is_turned_off_not_deleted(session: Session) -> None:
    """원칙 ⑦의 코드판 — 끈 코드는 목록에서 빠지되 과거 기록에서는 읽힌다.

    지우면 그 코드로 적힌 기록이 뜻을 잃는다. 그래서 삭제 칸이 아예 없고,
    끄는 것은 값을 바꾸는 일이라 줄은 그대로 남는다.
    """
    session.add(_group())
    code = CommonCode(group_code=codes.UOM, code="L", name="리터")
    session.add(code)
    session.flush()
    assert code.is_active is True, "새 코드는 켜져 있어야 한다"

    code.is_active = False
    session.flush()

    still_there = session.get(CommonCode, (codes.UOM, "L"))
    assert still_there is not None, "끈 코드가 사라졌다 — 과거 기록이 뜻을 잃는다"
    assert still_there.name == "리터"


def test_a_new_code_sorts_last_by_default(session: Session) -> None:
    """정렬순서를 정하지 않아도 들어간다 — 사람이 매번 숫자를 고르지 않는다."""
    session.add(_group())
    code = CommonCode(group_code=codes.UOM, code="KG", name="킬로그램")
    session.add(code)
    session.flush()

    assert code.sort_order == 0
