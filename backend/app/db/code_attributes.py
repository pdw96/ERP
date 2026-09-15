"""공통코드에 딸린 속성 — 확장 표 셋과 「코드 × 단계」.

본체에는 모든 분류가 함께 쓰는 것만 두고, 코드마다 딸린 값은 그 코드를
참조하는 **작은 표**에 둔다. 전부 본체에 밀어 넣으면 대부분이 빈 칸이 되고
`attr1 … attr9` 로 끝난다.

속성이 붙는 그룹은 셋뿐이다 — 수불유형 · 불합격사유 · 미납종결사유. 나머지
그룹은 속성이 없어 본체만으로 끝난다.
"""

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class TxnTypeAttribute(Base):
    """확장 ① 수불유형 — 프로그램이 이 셋을 보고 원장을 센다.

    「사유 필수」와 「승인 필요」를 넣으려다 뺐다. 사유도 승인도 수불 줄이
    아니라 **근거 문서**(재고조정)의 성질이며, 수불 줄은 승인이 끝난 뒤에 나는
    결과다. 업무 문서가 원인이고 수불 줄은 결과다.
    """

    __tablename__ = "txn_type_attributes"
    __table_args__ = (
        *code_reference(
            group_column="group_code",
            code_column="code",
            group_code=codes.TXN_TYPE,
            name="txn_type_attribute",
        ),
        CheckConstraint(
            f"total_effect IN ({_quoted(codes.TOTAL_EFFECTS)})",
            name="ck_txn_type_attribute_effect",
        ),
        # 짝은 **이 표에 줄이 있는 수불유형**이어야 한다. 공통코드를 가리키면
        # 「그 코드가 있다」까지만 증명된다 — 속성 줄이 아예 없는 코드를 짝으로
        # 적어도 통과하고, 그러면 짝을 따라간 자리에 총량 영향도 근거 문서도
        # 없다. 여기를 가리키면 그 한 겹이 더 막힌다.
        #
        # **서로를 가리키는지까지는 제약이 보지 못한다.** A 가 B 를 적고 B 가 C 를
        # 적어도 두 줄 다 통과한다 — 같은 표의 다른 줄을 보는 조건은 CHECK 로
        # 적을 수 없다. 지금은 시드가 유일한 쓰기 경로라
        # `tests/test_seed.py::test_every_pair_in_the_seed_points_back` 가 심긴
        # 줄에서 그것을 지키고, 화면에서 코드를 만드는 길이 생기는 날 쓰기 시점
        # 검증이 함께 서야 한다. **이름을 적어 둔다** — 「테스트가 지킨다」고만
        # 적힌 규칙은 그 테스트가 없어도 읽는 사람이 알아채지 못한다.
        ForeignKeyConstraint(
            ["group_code", "paired_code"],
            ["txn_type_attributes.group_code", "txn_type_attributes.code"],
            name="fk_txn_type_attribute_pair",
        ),
        CheckConstraint("paired_code <> code", name="ck_txn_type_attribute_pair_not_self"),
    )

    group_code: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=codes.TXN_TYPE, server_default=codes.TXN_TYPE
    )
    code: Mapped[str] = mapped_column(String(30), primary_key=True)

    # 잔량의 합을 어떻게 세는가.
    total_effect: Mapped[str] = mapped_column(String(10))
    # 창고를 건너면 두 줄이 난다 — 생산출고 ↔ 생산입고가 서로를 가리키므로
    # 프로그램이 짝을 함께 만든다. 한쪽만 나는 사고를 구조가 막는다.
    paired_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 원장에서 「왜 이 줄이 났는가」로 내려가는 길. 유형을 사람이 고르지 않는
    # 이유이기도 하다 — 화면이 유형을 정한다는 규칙의 반대 방향 기록이다.
    source_document_type: Mapped[str] = mapped_column(String(30))


class NonconformityAttribute(Base):
    """확장 ② 불합격사유 — 코드에 둘.

    **목록을 두 벌 두지 않는다.** 열아홉 중 열넷은 검사 항목에서 따라 나오고
    손으로 유지하는 것은 계수 넷뿐이다. 계량 코드가 항목을 가리키면 둘이 갈릴
    수 없다 — 항목에 「접착력」을 넣고 코드 표에 그것이 없으면 불합격을 적을
    수가 없고, 반대로 하면 쓰이지 않는 코드가 남는다.
    """

    __tablename__ = "nonconformity_attributes"
    __table_args__ = (
        *code_reference(
            group_column="group_code",
            code_column="code",
            group_code=codes.NC_REASON,
            name="nonconformity_attribute",
        ),
        *code_reference(
            group_column="inspection_item_group",
            code_column="inspection_item_code",
            group_code=codes.INSP_ITEM,
            name="nonconformity_attribute_item",
        ),
        CheckConstraint(
            f"measure_kind IN ({_quoted(codes.MEASURE_KINDS)})",
            name="ck_nonconformity_attribute_kind",
        ),
        # 계량이면 검사 항목이 있어야 한다 — 그 코드는 항목의 판정 결과일 뿐이다.
        # 계수는 재는 것이 아니라 세는 것이라 가리킬 항목이 없을 수 있다.
        CheckConstraint(
            f"measure_kind <> '{codes.MEASURED_KIND}' OR inspection_item_code IS NOT NULL",
            name="ck_nonconformity_attribute_measured_needs_item",
        ),
    )

    group_code: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=codes.NC_REASON, server_default=codes.NC_REASON
    )
    code: Mapped[str] = mapped_column(String(30), primary_key=True)

    measure_kind: Mapped[str] = mapped_column(String(10))
    inspection_item_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    inspection_item_group: Mapped[str] = mapped_column(
        String(20), default=codes.INSP_ITEM, server_default=codes.INSP_ITEM
    )


class NonconformityStageRule(Base):
    """처분 기본값은 코드가 아니라 **「코드 × 단계」**에 붙는다.

    같은 코드인데 처분이 다르다 — 두께 규격 이탈은 FQC 에서 나면 재작업이고
    OQC 에서 나면 등급 하향이다. 로트 부여 시점이 그것을 가른다.

    **줄이 있는 것 자체가 「그 단계에서 쓸 수 있는 코드」라는 뜻**이므로 별도의
    「적용 단계」 칸이 없다 — 검사 대기를 기록의 부재로 표현하는 것과 같은
    방식이다.
    """

    __tablename__ = "nonconformity_stage_rules"
    __table_args__ = (
        # **속성 줄이 있는 사유만** 단계에 걸 수 있다. 공통코드를 가리키면
        # 「그 코드가 있다」까지만 증명된다 — `measure_kind` 도 검사 항목도 없는
        # 사유가 단계에서 쓸 수 있게 되고, 검사원이 그것을 고르면 다음 화면이
        # 무엇을 할지 모른다. 수불유형의 짝에서 쓴 것과 같은 한 겹이다.
        ForeignKeyConstraint(
            ["reason_group", "reason_code"],
            ["nonconformity_attributes.group_code", "nonconformity_attributes.code"],
            name="fk_nonconformity_stage_rule_reason",
        ),
        CheckConstraint(
            f"reason_group = '{codes.NC_REASON}'",
            name="ck_nonconformity_stage_rule_reason_group",
        ),
        *code_reference(
            group_column="stage_group",
            code_column="stage_code",
            group_code=codes.INSP_STAGE,
            name="nonconformity_stage_rule_stage",
        ),
        CheckConstraint(
            f"disposition IN ({_quoted(codes.DISPOSITIONS)})",
            name="ck_nonconformity_stage_rule_disposition",
        ),
    )

    reason_group: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=codes.NC_REASON, server_default=codes.NC_REASON
    )
    reason_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    stage_group: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        default=codes.INSP_STAGE,
        server_default=codes.INSP_STAGE,
    )
    stage_code: Mapped[str] = mapped_column(String(30), primary_key=True)

    disposition: Mapped[str] = mapped_column(String(20))
    special_acceptance_allowed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class PurchaseCloseAttribute(Base):
    """확장 ③ 미납종결사유 — 칸 셋.

    **「성적 반영 여부」 칸이 없다.** 성적 축이 비어 있는가로 그대로 나오기
    때문이다 — 축이 있으면 반영이고 없으면 아니다. 따로 두면 둘이 어긋날 수
    있고, 어긋나면 단종처럼 예외인 줄에서 어긋난다.
    """

    __tablename__ = "purchase_close_attributes"
    __table_args__ = (
        *code_reference(
            group_column="group_code",
            code_column="code",
            group_code=codes.PO_CLOSE,
            name="purchase_close_attribute",
        ),
        CheckConstraint(
            f"responsibility IN ({_quoted(codes.RESPONSIBILITIES)})",
            name="ck_purchase_close_attribute_responsibility",
        ),
        CheckConstraint(
            f"scorecard_axis IS NULL OR scorecard_axis IN ({_quoted(codes.SCORECARD_AXES)})",
            name="ck_purchase_close_attribute_axis",
        ),
        CheckConstraint(
            f"reorder_default IN ({_quoted(codes.REORDER_DEFAULTS)})",
            name="ck_purchase_close_attribute_reorder",
        ),
        # **성적 축은 공급사 책임일 때만 붙는다.** 자사 사유에 축이 달리면
        # 계획이 줄어 종결한 것까지 공급사 성적에 섞이고, 성적이 망가진다.
        # 반대는 열려 있다 — 공급사 책임이어도 축이 없을 수 있다(단종).
        CheckConstraint(
            f"scorecard_axis IS NULL OR responsibility = '{codes.SUPPLIER}'",
            name="ck_purchase_close_attribute_axis_needs_supplier",
        ),
    )

    group_code: Mapped[str] = mapped_column(
        String(20), primary_key=True, default=codes.PO_CLOSE, server_default=codes.PO_CLOSE
    )
    code: Mapped[str] = mapped_column(String(30), primary_key=True)

    responsibility: Mapped[str] = mapped_column(String(10))
    # 비어 있으면 공급사 성적에 잡히지 않는다.
    scorecard_axis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reorder_default: Mapped[str] = mapped_column(String(10))
