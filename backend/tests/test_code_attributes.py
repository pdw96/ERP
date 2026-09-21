"""확장 표 셋과 「코드 × 단계」 — 조각 3."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import codes
from app.db.code_attributes import (
    NonconformityAttribute,
    NonconformityStageRule,
    PurchaseCloseAttribute,
    TxnTypeAttribute,
)
from tests.factories import add_code


def _usable_reason(session: Session, code: str, name: str, item: str | None = None) -> None:
    """단계에 걸 수 있는 사유 하나 — **속성 줄까지** 세운다.

    코드만 있고 속성이 없는 사유는 단계에 걸 수 없다. 그것이 제약이다.
    """
    add_code(session, codes.NC_REASON, code, name)
    if item is not None:
        add_code(session, codes.INSP_ITEM, item)
    session.flush()
    session.add(
        NonconformityAttribute(
            code=code,
            measure_kind=codes.MEASURED_KIND if item else codes.COUNTED_KIND,
            inspection_item_code=item,
        )
    )
    session.flush()


# ── 그룹이 고정되는가 ───────────────────────────────────────────────────────


def test_an_extension_row_cannot_point_at_another_group(session: Session) -> None:
    """공통코드로 모으면 타입이 사라진다 — 그것을 제약이 되받는다.

    `common_codes.code` 를 그냥 가리키면 어느 그룹의 코드든 받는다. 「이 칸에는
    수불유형만」이 문서가 아니라 데이터베이스에 있어야 한다.
    """
    add_code(session, codes.UOM, "EA", "개")
    session.flush()

    session.add(
        TxnTypeAttribute(
            group_code=codes.UOM,  # 수불유형이 아니다
            code="EA",
            total_effect=codes.EFFECT_INCREASE,
            source_document_type="재고이동 처리",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_an_extension_row_needs_the_code_to_exist(session: Session) -> None:
    """속성은 코드에 딸린 것이다 — 코드가 없으면 딸릴 곳이 없다."""
    session.add(
        TxnTypeAttribute(
            code="없는코드",
            total_effect=codes.EFFECT_INCREASE,
            source_document_type="재고이동 처리",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# ── 확장 ① 수불유형 ────────────────────────────────────────────────────────


def test_a_pair_must_be_a_transaction_type_that_has_attributes(session: Session) -> None:
    """짝은 **이 표에 줄이 있는** 수불유형이어야 한다.

    공통코드를 가리키면 「그 코드가 있다」까지만 증명된다 — 속성 줄이 없는
    코드를 짝으로 적어도 통과하고, 짝을 따라간 자리에 총량 영향도 근거 문서도
    없다.
    """
    add_code(session, codes.TXN_TYPE, "생산출고")
    add_code(session, codes.TXN_TYPE, "생산입고")
    session.flush()

    # 「생산입고」는 코드로는 있지만 아직 속성 줄이 없다.
    session.add(
        TxnTypeAttribute(
            code="생산출고",
            total_effect=codes.EFFECT_DECREASE,
            paired_code="생산입고",
            source_document_type="재고이동 처리",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_two_transaction_types_can_point_at_each_other(session: Session) -> None:
    """창고를 건너면 두 줄이 난다 — 한쪽만 나는 사고를 구조가 막는다."""
    add_code(session, codes.TXN_TYPE, "생산출고")
    add_code(session, codes.TXN_TYPE, "생산입고")
    session.flush()

    session.add(
        TxnTypeAttribute(
            code="생산출고",
            total_effect=codes.EFFECT_DECREASE,
            source_document_type="재고이동 처리",
        )
    )
    session.add(
        TxnTypeAttribute(
            code="생산입고",
            total_effect=codes.EFFECT_INCREASE,
            paired_code="생산출고",
            source_document_type="재고이동 처리",
        )
    )
    session.flush()

    outbound = session.get(TxnTypeAttribute, (codes.TXN_TYPE, "생산출고"))
    assert outbound is not None
    outbound.paired_code = "생산입고"
    session.flush()  # 서로를 가리키는 것이 정상이다


def test_a_transaction_type_cannot_pair_with_itself(session: Session) -> None:
    """자기를 짝으로 두면 창고를 건넌 두 줄이 한 줄이 된다."""
    add_code(session, codes.TXN_TYPE, "재고조정")
    session.flush()

    session.add(
        TxnTypeAttribute(
            code="재고조정",
            total_effect=codes.EFFECT_BOTH,
            paired_code="재고조정",
            source_document_type="재고조정",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_carry_forward_is_a_baseline_not_an_increase(session: Session) -> None:
    """「기준점」은 전기이월이다 — 잔량은 그 줄부터 더한다.

    증가로 두면 이월이 재고를 늘린 것처럼 읽히고, 이월 전 줄을 함께 더하면
    같은 수량이 두 번 세어진다.
    """
    add_code(session, codes.TXN_TYPE, "전기이월")
    session.flush()

    session.add(
        TxnTypeAttribute(
            code="전기이월",
            total_effect=codes.EFFECT_BASELINE,
            source_document_type="월말 마감",
        )
    )
    session.flush()

    row = session.get(TxnTypeAttribute, (codes.TXN_TYPE, "전기이월"))
    assert row is not None
    assert row.total_effect == codes.EFFECT_BASELINE


def test_an_unknown_total_effect_is_refused(session: Session) -> None:
    """총량 영향은 프로그램이 분기하는 값이다 — 모르는 값이면 셀 수 없다."""
    add_code(session, codes.TXN_TYPE, "구매입고")
    session.flush()

    session.add(
        TxnTypeAttribute(
            code="구매입고", total_effect="조금 늘어남", source_document_type="가입고"
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


# ── 확장 ② 불합격사유 ──────────────────────────────────────────────────────


def test_a_measured_reason_must_name_its_inspection_item(session: Session) -> None:
    """**목록을 두 벌 두지 않는다.**

    계량 코드는 항목의 판정 결과일 뿐이다. 가리키지 않으면 항목 표와 코드 표가
    갈리고, 갈리면 불합격을 적을 수 없는 항목이나 쓰이지 않는 코드가 남는다.
    """
    add_code(session, codes.NC_REASON, "FQ-THK", "두께 규격 이탈")
    session.flush()

    session.add(NonconformityAttribute(code="FQ-THK", measure_kind=codes.MEASURED_KIND))
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_counted_reason_may_stand_alone(session: Session) -> None:
    """계수는 재는 것이 아니라 세는 것이라 가리킬 항목이 없을 수 있다.

    시드의 계수 코드는 다섯이고(`IQ-FM` · `IQ-EXP` · `IQ-PKG` · `IQ-DOC` · `FQ-FM`)
    그중 가리킬 항목이 없는 것이 `IQ-EXP` 다.
    """
    add_code(session, codes.NC_REASON, "IQ-DOC", "시험성적서 미비")
    session.flush()

    session.add(NonconformityAttribute(code="IQ-DOC", measure_kind=codes.COUNTED_KIND))
    session.flush()


def test_a_measured_reason_links_to_a_real_item(session: Session) -> None:
    """가리키는 항목은 검사항목 그룹에 실제로 있어야 한다."""
    add_code(session, codes.NC_REASON, "FQ-THK", "두께 규격 이탈")
    add_code(session, codes.INSP_ITEM, "두께")
    session.flush()

    session.add(
        NonconformityAttribute(
            code="FQ-THK",
            measure_kind=codes.MEASURED_KIND,
            inspection_item_code="두께",
        )
    )
    session.flush()

    row = session.get(NonconformityAttribute, (codes.NC_REASON, "FQ-THK"))
    assert row is not None
    assert row.inspection_item_code == "두께"


# ── 처분 기본값은 「코드 × 단계」에 붙는다 ──────────────────────────────────


def test_the_same_reason_disposes_differently_by_stage(session: Session) -> None:
    """같은 코드인데 처분이 다르다 — 로트 부여 시점이 그것을 가른다.

    두께 규격 이탈은 FQC 에서 나면 재작업이고 OQC 에서 나면 등급 하향이다.
    처분을 코드에 붙였다면 이 두 줄을 적을 수 없다.
    """
    _usable_reason(session, "FQ-THK", "두께 규격 이탈", item="두께")
    add_code(session, codes.INSP_STAGE, "FQC")
    add_code(session, codes.INSP_STAGE, "OQC")
    session.flush()

    session.add(
        NonconformityStageRule(reason_code="FQ-THK", stage_code="FQC", disposition="재작업")
    )
    session.add(
        NonconformityStageRule(reason_code="FQ-THK", stage_code="OQC", disposition="등급 하향")
    )
    session.flush()

    rows = {
        row.stage_code: row.disposition for row in session.query(NonconformityStageRule).all()
    }
    assert rows == {"FQC": "재작업", "OQC": "등급 하향"}


def test_a_row_is_what_makes_a_reason_usable_in_a_stage(session: Session) -> None:
    """**줄이 있는 것 자체가 「그 단계에서 쓸 수 있는 코드」라는 뜻**이다.

    그래서 「적용 단계」 칸이 따로 없다 — 검사 대기를 기록의 부재로 표현하는
    것과 같은 방식이다.
    """
    _usable_reason(session, "IQ-FM", "이물 혼입")
    add_code(session, codes.INSP_STAGE, "IQC")
    add_code(session, codes.INSP_STAGE, "OQC")
    session.flush()

    session.add(
        NonconformityStageRule(reason_code="IQ-FM", stage_code="IQC", disposition="반품")
    )
    session.flush()

    assert (
        session.get(NonconformityStageRule, (codes.NC_REASON, "IQ-FM", codes.INSP_STAGE, "OQC"))
        is None
    )
    columns = {column.name for column in NonconformityStageRule.__table__.columns}
    assert "applies_to_stage" not in columns


def test_special_acceptance_is_off_unless_someone_allows_it(session: Session) -> None:
    """특채는 「불합격인데 쓰기로 한 결정」이다 — 기본이 허용이면 결정이 아니다."""
    _usable_reason(session, "IQ-FM", "이물 혼입")
    add_code(session, codes.INSP_STAGE, "IQC")
    session.flush()

    rule = NonconformityStageRule(reason_code="IQ-FM", stage_code="IQC", disposition="반품")
    session.add(rule)
    session.flush()

    assert rule.special_acceptance_allowed is False


def test_an_unknown_disposition_is_refused(session: Session) -> None:
    """처분은 다섯뿐이다 — 검사원의 다음 화면이 이 값으로 갈린다."""
    _usable_reason(session, "IQ-FM", "이물 혼입")
    add_code(session, codes.INSP_STAGE, "IQC")
    session.flush()

    session.add(
        NonconformityStageRule(reason_code="IQ-FM", stage_code="IQC", disposition="보류")
    )
    with pytest.raises(IntegrityError):
        session.flush()


# ── 확장 ③ 미납종결사유 ────────────────────────────────────────────────────


def test_an_empty_axis_means_it_does_not_count_against_the_supplier(
    session: Session,
) -> None:
    """단종은 공급사 쪽인데 성적에는 잡히지 않는다 — 공급사의 잘못이 아니다.

    「성적 반영 여부」 칸을 따로 두지 않는 이유가 이 줄이다. 두 값이 어긋나면
    바로 이런 예외에서 어긋난다.
    """
    add_code(session, codes.PO_CLOSE, "PO-EOL", "단종")
    session.flush()

    session.add(
        PurchaseCloseAttribute(
            code="PO-EOL",
            responsibility="공급사",
            scorecard_axis=None,
            reorder_default="건별",
        )
    )
    session.flush()

    row = session.get(PurchaseCloseAttribute, (codes.PO_CLOSE, "PO-EOL"))
    assert row is not None
    assert row.scorecard_axis is None

    columns = {column.name for column in PurchaseCloseAttribute.__table__.columns}
    assert "counts_toward_scorecard" not in columns, "축에서 파생되는 값을 따로 저장했다"


def test_an_unknown_scorecard_axis_is_refused(session: Session) -> None:
    """성적은 넷으로 갈린다 — 축이 늘면 집계가 갈 곳을 잃는다."""
    add_code(session, codes.PO_CLOSE, "PO-SHT", "수량 부족")
    session.flush()

    session.add(
        PurchaseCloseAttribute(
            code="PO-SHT",
            responsibility="공급사",
            scorecard_axis="친절도",
            reorder_default="필요",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_reason_without_attributes_cannot_be_used_in_a_stage(session: Session) -> None:
    """**속성 줄이 없는 사유는 단계에 걸 수 없다.**

    공통코드를 가리키면 「그 코드가 있다」까지만 증명된다 — `measure_kind` 도
    검사 항목도 없는 사유가 단계에서 쓸 수 있게 되고, 검사원이 그것을 고르면
    다음 화면이 무엇을 할지 모른다.
    """
    add_code(session, codes.NC_REASON, "ZZ-TMP", "속성 없는 사유")
    add_code(session, codes.INSP_STAGE, "IQC")
    session.flush()

    session.add(
        NonconformityStageRule(reason_code="ZZ-TMP", stage_code="IQC", disposition="반품")
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_a_scorecard_axis_needs_the_supplier_to_be_responsible(session: Session) -> None:
    """자사 사유에 성적 축이 달리면 **공급사가 우리 탓으로 벌점을 받는다.**

    계획이 줄어 종결한 것까지 성적에 섞이면 성적이 망가진다. 반대는 열려 있다 —
    공급사 책임이어도 축이 없을 수 있다(단종).
    """
    add_code(session, codes.PO_CLOSE, "PO-CHG", "소요량 감소")
    session.flush()

    session.add(
        PurchaseCloseAttribute(
            code="PO-CHG",
            responsibility="자사",
            scorecard_axis="수량 준수율",
            reorder_default="불필요",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
