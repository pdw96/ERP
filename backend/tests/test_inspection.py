"""검사 기록 — 조각 8.

**이 표가 로트를 만든다.** 그래서 여기서 검사하는 것은 칸이 아니라 **원칙 ① 이
구조로 서 있는가**다 — 「불합격은 로트를 만들지 못하고, 예외는 특채 하나이며,
특채는 아무 사유로나 열리지 않는다」.

로트를 실제로 만드는 쪽(측정값 줄 · 수불 원장)은 아직 없다. 지금 검사할 수 있는
것은 **판정이 설 수 있는 모양**이고, 그것이 제약으로 서 있지 않으면 뒤에 오는
조각이 주석을 믿고 짓게 된다.
"""

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import NonconformityAttribute, NonconformityStageRule
from app.db.inspection import Inspection
from app.db.master import Item, Partner
from tests.factories import add_code, make_item, make_partner, prepare_item_codes

# 시드의 IQC 사유 가운데 특채가 열린 것과 닫힌 것 하나씩.
REASON_OPEN = "IQ-VIS"
REASON_CLOSED = "IQ-PSD"
# 다른 단계의 사유 — IQC 에는 짝이 없다.
REASON_OTHER_STAGE = "FQ-THK"


def _reason(
    session: Session,
    code: str,
    item: str,
    *,
    stage: str,
    special_acceptance_allowed: bool,
) -> None:
    """사유 하나를 **속성 줄과 단계 줄까지** 세운다.

    코드만 있고 속성이 없는 사유는 단계에 걸 수 없고, 단계 줄이 없는 사유는
    검사 기록이 가리킬 수 없다. 세 겹이 다 서야 한 줄이 쓸 수 있는 사유가 된다.
    """
    add_code(session, codes.NC_REASON, code, code)
    add_code(session, codes.INSP_ITEM, item)
    session.flush()
    session.add(
        NonconformityAttribute(
            code=code, measure_kind=codes.MEASURED_KIND, inspection_item_code=item
        )
    )
    session.flush()
    session.add(
        NonconformityStageRule(
            reason_code=code,
            stage_code=stage,
            disposition="반품",
            special_acceptance_allowed=special_acceptance_allowed,
        )
    )
    session.flush()


@pytest.fixture
def prepared(session: Session) -> Session:
    """검사 한 줄이 서는 데 필요한 최소 기준정보."""
    prepare_item_codes(session)
    add_code(session, codes.INSP_STAGE, codes.STAGE_INCOMING, "수입검사")
    add_code(session, codes.INSP_STAGE, "FQC", "최종검사")
    material = make_item(codes.RAW_MATERIAL, code="RM-01")
    finished = make_item(codes.FINISHED_GOODS, code="FG-01")
    supplier = make_partner(codes.SUPPLIER, code="SUP-01")
    session.add_all([material, finished, supplier])
    session.flush()

    _reason(
        session,
        REASON_OPEN,
        "점도",
        stage=codes.STAGE_INCOMING,
        special_acceptance_allowed=True,
    )
    _reason(
        session,
        REASON_CLOSED,
        "입도",
        stage=codes.STAGE_INCOMING,
        special_acceptance_allowed=False,
    )
    _reason(session, REASON_OTHER_STAGE, "두께", stage="FQC", special_acceptance_allowed=True)
    return session


def _material(session: Session) -> Item:
    return session.query(Item).filter_by(code="RM-01").one()


def _supplier(session: Session) -> Partner:
    return session.query(Partner).filter_by(code="SUP-01").one()


def _inspection(session: Session, **overrides: object) -> Inspection:
    """제약을 통과하는 합격 검사 하나. 넘긴 값만 달라진다."""
    item = _material(session)
    partner = _supplier(session)
    fields: dict[str, object] = {
        "item_id": item.id,
        "item_type": item.item_type,
        # 자재군은 품목이 아는 사실이다 — 쓰는 쪽이 지어내지 않고 끌어온다.
        "material_group": item.material_group,
        "supplier_id": partner.id,
        "supplier_type": partner.partner_type,
        "supplier_lot_number": "SL-2026-0001",
        "quantity": 500.0,
        "judged_at": datetime(2026, 9, 21, 9, 0),
        "judged_by": "검사원 1",
        "result": codes.JUDGMENT_PASSED,
    }
    fields.update(overrides)
    return Inspection(**fields)


# ── 판정 셋이 선다 ──────────────────────────────────────────────────────────


def test_a_passing_inspection_carries_no_reason(prepared: Session) -> None:
    """합격은 사유를 갖지 않는다 — 무엇이 합격인지 사유가 말할 것이 없다."""
    prepared.add(_inspection(prepared))
    prepared.flush()

    row = prepared.query(Inspection).one()
    assert row.result == codes.JUDGMENT_PASSED
    assert row.nonconformity_code is None
    assert row.special_acceptance_allowed is None
    # 단계 칸은 데이터가 아니라 구조다 — 적지 않아도 채워진다.
    assert row.inspection_stage == codes.STAGE_INCOMING


def test_a_failing_inspection_names_its_reason(prepared: Session) -> None:
    """떨어졌으면 왜 떨어졌는지 표가 말한다."""
    prepared.add(
        _inspection(prepared, result=codes.JUDGMENT_FAILED, nonconformity_code=REASON_CLOSED)
    )
    prepared.flush()

    row = prepared.query(Inspection).one()
    assert row.nonconformity_code == REASON_CLOSED
    # **특채가 아니므로 비어 있다.** 특채를 열지 않은 줄이 특채의 근거를 들고
    # 있으면 그것은 다른 사실이다.
    assert row.special_acceptance_allowed is None


def test_a_special_acceptance_stands_on_a_reason_that_opens_it(prepared: Session) -> None:
    """특채는 예외 하나이고, 그 예외가 서는 자리가 여기다."""
    prepared.add(
        _inspection(
            prepared,
            result=codes.JUDGMENT_SPECIAL,
            nonconformity_code=REASON_OPEN,
            special_acceptance_allowed=True,
        )
    )
    prepared.flush()

    row = prepared.query(Inspection).one()
    assert row.result == codes.JUDGMENT_SPECIAL
    assert row.special_acceptance_allowed is True


# ── 특채를 여는 것은 구조다 ─────────────────────────────────────────────────


def test_a_special_acceptance_cannot_stand_on_a_closed_reason(prepared: Session) -> None:
    """**원칙 ① 의 예외가 딱 하나인 것을 외래키가 지킨다.**

    「특채는 `special_acceptance_allowed` 가 켜진 사유만」이 주석이면 다음 조각이
    그것을 믿고 짓는다. 여기서 막히지 않으면 입도 이탈이 특채로 들어오고,
    그 로트는 만들어진 뒤에는 되돌릴 수 없다.
    """
    prepared.add(
        _inspection(
            prepared,
            result=codes.JUDGMENT_SPECIAL,
            nonconformity_code=REASON_CLOSED,
            special_acceptance_allowed=True,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_special_acceptance_cannot_disown_the_flag(prepared: Session) -> None:
    """칸을 비워 **외래키를 건너뛰는** 길을 CHECK 가 막는다.

    복합 외래키는 한 칸이라도 `NULL` 이면 검사하지 않는다. 그래서 특채인데
    플래그를 비우면 「켜진 사유인가」를 아무도 보지 않게 된다 — 그 문을 닫는
    것이 「특채일 때만, 특채이면 반드시」라는 양방향 CHECK 다.
    """
    prepared.add(
        _inspection(prepared, result=codes.JUDGMENT_SPECIAL, nonconformity_code=REASON_OPEN)
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_non_special_row_cannot_carry_the_flag(prepared: Session) -> None:
    """특채가 아닌 줄은 특채의 근거를 들지 않는다 — 양방향의 반대쪽."""
    prepared.add(
        _inspection(
            prepared,
            result=codes.JUDGMENT_FAILED,
            nonconformity_code=REASON_OPEN,
            special_acceptance_allowed=True,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_flag_cannot_be_written_false(prepared: Session) -> None:
    """거짓은 **외래키가 통과시킨다** — 짝이 실재하기 때문이다.

    `(IQ-PSD, IQC, FALSE)` 는 기준 표에 있는 줄이다. 그래서 특채 줄이 거짓을
    적으면 외래키는 아무 말도 하지 않고, 「특채가 닫힌 사유로 낸 특채」가 선다.
    그 자리를 CHECK 가 따로 막는다.
    """
    prepared.add(
        _inspection(
            prepared,
            result=codes.JUDGMENT_SPECIAL,
            nonconformity_code=REASON_CLOSED,
            special_acceptance_allowed=False,
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_granted_special_acceptance_freezes_the_rule_it_stood_on(prepared: Session) -> None:
    """**일어난 일은 지우지 않는다** — 원칙 ⑦ 이 기준정보 쪽에서도 한 겹 선다.

    특채를 이미 낸 사유의 플래그를 끄면 그 검사가 가리키던 짝이 사라진다.
    외래키가 그 수정을 막으므로, 「그때는 특채가 열려 있었다」가 조용히
    거짓이 되지 않는다.
    """
    prepared.add(
        _inspection(
            prepared,
            result=codes.JUDGMENT_SPECIAL,
            nonconformity_code=REASON_OPEN,
            special_acceptance_allowed=True,
        )
    )
    prepared.flush()

    with pytest.raises(IntegrityError):
        prepared.execute(
            text(
                "UPDATE nonconformity_stage_rules SET special_acceptance_allowed = FALSE"
                " WHERE reason_code = :code AND stage_code = :stage"
            ),
            {"code": REASON_OPEN, "stage": codes.STAGE_INCOMING},
        )


def test_an_unused_rule_may_still_be_closed(prepared: Session) -> None:
    """**특채를 낸 적이 없는 사유는 그대로 끈다.**

    앞의 테스트가 막는 것은 「이미 일어난 일」이지 기준정보 유지보수가 아니다.
    둘을 가르지 않으면 이 표는 한 번 켠 플래그를 영영 못 끄는 표가 된다.
    """
    prepared.execute(
        text(
            "UPDATE nonconformity_stage_rules SET special_acceptance_allowed = FALSE"
            " WHERE reason_code = :code AND stage_code = :stage"
        ),
        {"code": REASON_OPEN, "stage": codes.STAGE_INCOMING},
    )

    rule = prepared.get(
        NonconformityStageRule,
        (codes.NC_REASON, REASON_OPEN, codes.INSP_STAGE, codes.STAGE_INCOMING),
    )
    prepared.refresh(rule)
    assert rule.special_acceptance_allowed is False


# ── 사유는 그 단계의 것이어야 한다 ──────────────────────────────────────────


def test_a_reason_from_another_stage_is_refused(prepared: Session) -> None:
    """공통코드를 가리켰으면 통과했을 자리다.

    `FQ-THK` 는 실재하는 사유이고 코드 표에도 있다. 다만 **IQC 에서 쓸 수 있는
    사유가 아니다** — 처분도 특채 가부도 IQC 자리에 없으므로, 그것을 적은 검사는
    가리킬 곳이 없는 사유를 든 셈이 된다.
    """
    prepared.add(
        _inspection(
            prepared, result=codes.JUDGMENT_FAILED, nonconformity_code=REASON_OTHER_STAGE
        )
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 결과와 사유가 서로를 정한다 ─────────────────────────────────────────────


def test_a_passing_inspection_cannot_carry_a_reason(prepared: Session) -> None:
    """합격인데 사유가 있으면 무엇이 합격인지 알 수 없다."""
    prepared.add(_inspection(prepared, nonconformity_code=REASON_CLOSED))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_a_failing_inspection_cannot_omit_its_reason(prepared: Session) -> None:
    """떨어졌는데 사유가 없으면 표가 왜 떨어졌는지 말하지 못한다."""
    prepared.add(_inspection(prepared, result=codes.JUDGMENT_FAILED))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_result_must_be_one_of_three(prepared: Session) -> None:
    """넷째 판정이 생기는 것은 코드값이 느는 것이 아니라 원칙 ① 이 바뀌는 것이다.

    **사유를 함께 적는다.** 「보류」는 합격이 아니므로 사유를 비우면 결과·사유
    CHECK 가 **먼저** 물고, 그러면 이 테스트는 통과하면서도 판정 목록을 지키는
    제약이 실제로 서 있는지는 한 번도 묻지 않게 된다 — 물게 하는 제약을 직접
    읽어 확인했다.
    """
    prepared.add(_inspection(prepared, result="보류", nonconformity_code=REASON_CLOSED))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 무엇을 · 누구에게 ───────────────────────────────────────────────────────


def test_only_a_raw_material_passes_the_incoming_gate(prepared: Session) -> None:
    """관문 1 이 보는 것은 원자재뿐이다 — 사 온 적 없는 완제품은 수입검사가 없다."""
    finished = prepared.query(Item).filter_by(code="FG-01").one()

    prepared.add(_inspection(prepared, item_id=finished.id, item_type=finished.item_type))
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_the_partner_must_be_a_supplier(prepared: Session) -> None:
    """고객사에게 자재를 받지는 않는다."""
    customer = make_partner(codes.CUSTOMER, code="CUS-01")
    prepared.add(customer)
    prepared.flush()

    prepared.add(
        _inspection(prepared, supplier_id=customer.id, supplier_type=customer.partner_type)
    )
    with pytest.raises(IntegrityError):
        prepared.flush()


def test_another_stage_cannot_be_written_yet(prepared: Session) -> None:
    """**이 조각은 관문 1 뿐이다.**

    받아 두면 판정 경로가 없는 줄이 서고, 화면에서는 검사받은 것처럼 보인다.
    관문 2 가 오는 날 이 CHECK 를 넓히는 마이그레이션이 함께 온다.
    """
    add_code(prepared, codes.INSP_STAGE, "OQC")
    prepared.flush()

    prepared.add(_inspection(prepared, inspection_stage="OQC"))
    with pytest.raises(IntegrityError):
        prepared.flush()


# ── 값이 뜻을 갖는가 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("blank", ["", " ", "\t", "　", "   "])
def test_the_judge_must_leave_a_name(prepared: Session, blank: str) -> None:
    """`btrim` 의 기본은 스페이스만 깎는다 — 탭과 전각 공백이 통과한다.

    판정자가 비어 있으면 **누가 그 로트를 만들었는지 아무도 모른다.** 사용자
    표가 없는 지금은 이 칸이 유일한 기록이다.
    """
    prepared.add(_inspection(prepared, judged_by=blank))
    with pytest.raises(IntegrityError):
        prepared.flush()


@pytest.mark.parametrize("blank", ["", " ", "\t", "　"])
def test_the_supplier_lot_number_must_be_present(prepared: Session, blank: str) -> None:
    """공급사 번호가 비어 보이면 어느 로트를 받았는지 되짚을 수 없다."""
    prepared.add(_inspection(prepared, supplier_lot_number=blank))
    with pytest.raises(IntegrityError):
        prepared.flush()


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_the_quantity_must_be_a_number_you_can_count(prepared: Session, bad: float) -> None:
    """`NaN >= 0` 이 참이라 하한만으로는 막지 못한다.

    한 줄이 들어오면 이후의 모든 합계가 `NaN` 이 되고 비교가 전부 거짓이라
    **재고가 조용히 사라진다.** 무한대도 같은 이유로 막는다.
    """
    prepared.add(_inspection(prepared, quantity=bad))
    with pytest.raises(IntegrityError):
        prepared.flush()
