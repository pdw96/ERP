"""검사 기록 — 관문 1 수입검사 한 건.

**이 표가 로트를 만든다.** 원칙 ① 이 「재고 로트는 합격 후에 생긴다」이므로
로트를 만드는 것은 입고가 아니라 **판정**이고, 그 판정이 여기 산다.

판정은 셋이다 — 합격 · 불합격 · 특채. 로트가 서는 것은 합격과 특채뿐이며,
**특채는 아무 사유로나 열리지 않는다.** 그것을 주석이 아니라 외래키가 막는
방법은 아래 「특채를 여는 것은 구조다」에 있다.

**판정자는 칸이고 표가 아니다.** 사람이 늘어 사용자 표가 서는 날 외래키로
승격한다 — 지금 권한 체계를 정하면 사람이 늘지도 않았는데 그 층을 미리 당기는
것이 된다.

**이 조각은 IQC 하나다.** 단계 칸이 있지만 값은 못박혀 있다 — 관문 2 는 범위
밖이고, 받을 수 없는 단계를 받는 칸은 빈 기준정보와 같다. 넓히는 것은
마이그레이션이다.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference, is_finite, is_present


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Inspection(Base):
    """검사 한 건 — 무엇을 · 누구에게 받아 · 누가 · 어떻게 판정했는가.

    **측정값은 여기 없다.** 항목마다 한 줄씩 서는 것이라 측정값 표가 따로
    든다. 여기 있는 것은 그 줄들이 모여 나온 **한 건의 판정**이다.

    ### 판정을 저장하는 이유 — 파생값 금지의 그 예외다

    원칙은 「파생값은 저장하지 않는다」이고 예외는 하나다 — **「그 판정의 근거가
    되었고 밖으로 나간 값」.** `result` 는 그 예외에 정확히 해당한다: 그 판정이
    로트를 만들었기 때문이다. 기준이 나중에 바뀌어도 **그때 그 판정은 그대로
    남아야 한다.**

    ### 특채를 여는 것은 구조다

    「특채는 `special_acceptance_allowed` 가 켜진 사유로만」이 이 표의 유일한
    예외 조항이고, 그것을 **두 외래키와 CHECK 하나**가 함께 건다.

    - 사유가 있는 줄은 `(사유 × 단계)` 로 `nonconformity_stage_rules` 를
      가리킨다 — **그 단계에서 쓸 수 있는 사유**만 적힌다. 공통코드를 가리키면
      「그 코드가 있다」까지만 증명된다
    - 특채인 줄은 **플래그까지 더해** 같은 표를 한 번 더 가리킨다. 그 짝은 켜진
      줄에만 있으므로, 꺼진 사유로 특채를 적으면 외래키가 거부한다
    - CHECK 가 「특채일 때만 그 칸이 차고, 차면 참이다」를 못박는다. 그것이
      없으면 특채 줄이 칸을 비워 두는 것으로 둘째 외래키를 건너뛴다
    """

    __tablename__ = "inspections"
    __table_args__ = (
        # ── 단계 ────────────────────────────────────────────────────────────
        *code_reference(
            group_column="stage_group",
            code_column="inspection_stage",
            group_code=codes.INSP_STAGE,
            name="inspection_stage",
        ),
        # **이 조각은 관문 1 뿐이다.** 다른 단계를 받아 두면 판정 경로가 없는
        # 줄이 서고, 그것은 화면에서 검사받은 것처럼 보인다. 관문 2 가 오는 날
        # 이 CHECK 를 넓히는 마이그레이션이 함께 온다.
        CheckConstraint(
            f"inspection_stage = '{codes.STAGE_INCOMING}'",
            name="ck_inspection_stage_is_incoming",
        ),
        # ── 무엇을 검사했는가 ───────────────────────────────────────────────
        ForeignKeyConstraint(
            ["item_id", "item_type"],
            ["items.id", "items.item_type"],
            name="fk_inspection_item",
        ),
        # **자재군은 품목에서 따라온다.** 지어낼 수 있는 값이 아니라 그 품목이
        # 이미 아는 사실이고, 이 외래키가 둘이 갈리는 것을 막는다 — `item_type`
        # 을 같은 방식으로 묶은 것과 같은 자리다.
        #
        # 이 칸이 여기 있는 이유는 **측정 줄**이다. 측정 줄이 「그 무리의 기준」만
        # 가리키게 하려면 검사와 기준이 같은 자재군을 말해야 하고, 그 묶음의
        # 가운데가 이 칸이다.
        ForeignKeyConstraint(
            ["item_id", "material_group"],
            ["items.id", "items.material_group"],
            name="fk_inspection_material_group",
        ),
        # **관문 1 이 보는 것은 원자재뿐이다.** 반제품과 완제품은 우리가 만드는
        # 것이라 수입검사를 받을 일이 없다 — 열어 두면 「사 온 적 없는 완제품의
        # 수입검사」가 선다.
        CheckConstraint(
            f"item_type = '{codes.RAW_MATERIAL}'",
            name="ck_inspection_item_is_raw_material",
        ),
        # ── 누구에게 받았는가 ───────────────────────────────────────────────
        ForeignKeyConstraint(
            ["supplier_id", "supplier_type"],
            ["partners.id", "partners.partner_type"],
            name="fk_inspection_supplier",
        ),
        CheckConstraint(
            f"supplier_type = '{codes.SUPPLIER}'", name="ck_inspection_is_supplier"
        ),
        # 공급사가 붙여 온 번호다. **비어 보이는 값을 받지 않는다** — `btrim` 의
        # 기본은 스페이스만 깎아 탭과 전각 공백을 통과시킨다.
        CheckConstraint(
            is_present("supplier_lot_number"),
            name="ck_inspection_supplier_lot_number_is_present",
        ),
        # ── 얼마를 ──────────────────────────────────────────────────────────
        # `NaN >= 0` 이 참이므로 하한만으로는 막지 못한다. 한 줄이 들어오면
        # 이후의 모든 합계가 `NaN` 이 되고 비교가 전부 거짓이라 재고가 조용히
        # 사라진다.
        CheckConstraint(
            f"quantity >= 0 AND {is_finite('quantity')}", name="ck_inspection_quantity"
        ),
        # ── 누가 ────────────────────────────────────────────────────────────
        CheckConstraint(is_present("judged_by"), name="ck_inspection_judged_by_is_present"),
        # ── 어떻게 판정했는가 ───────────────────────────────────────────────
        CheckConstraint(f"result IN ({_quoted(codes.JUDGMENTS)})", name="ck_inspection_result"),
        # **양방향이다.** 합격인데 사유가 있으면 무엇이 합격인지 알 수 없고,
        # 떨어졌는데 사유가 없으면 왜 떨어졌는지 표가 말하지 못한다. 한쪽만
        # 걸면 다른 쪽으로 새는 줄이 선다.
        CheckConstraint(
            f"(result = '{codes.JUDGMENT_PASSED}') = (nonconformity_code IS NULL)",
            name="ck_inspection_reason_matches_result",
        ),
        CheckConstraint(
            f"nonconformity_group = '{codes.NC_REASON}'",
            name="ck_inspection_nonconformity_group",
        ),
        # **그 단계에서 쓸 수 있는 사유만.** 공통코드를 가리키면 「그 코드가
        # 있다」까지만 증명된다 — IQC 검사에 FQC 사유를 적어도 통과하고, 그러면
        # 처분도 특채 가부도 없는 자리를 가리키게 된다.
        ForeignKeyConstraint(
            ["nonconformity_group", "nonconformity_code", "stage_group", "inspection_stage"],
            [
                "nonconformity_stage_rules.reason_group",
                "nonconformity_stage_rules.reason_code",
                "nonconformity_stage_rules.stage_group",
                "nonconformity_stage_rules.stage_code",
            ],
            name="fk_inspection_nonconformity",
        ),
        # ── 특채 ────────────────────────────────────────────────────────────
        # **원칙 ① 의 예외가 서는 단 한 자리다.** 같은 표를 플래그까지 더해 한 번
        # 더 가리키므로, 짝이 있는 것은 그 단계에서 **특채가 열린 사유**뿐이다.
        ForeignKeyConstraint(
            [
                "nonconformity_group",
                "nonconformity_code",
                "stage_group",
                "inspection_stage",
                "special_acceptance_allowed",
            ],
            [
                "nonconformity_stage_rules.reason_group",
                "nonconformity_stage_rules.reason_code",
                "nonconformity_stage_rules.stage_group",
                "nonconformity_stage_rules.stage_code",
                "nonconformity_stage_rules.special_acceptance_allowed",
            ],
            name="fk_inspection_special_acceptance",
        ),
        # **양방향이다.** 특채가 아닌데 차 있으면 특채를 열지 않은 줄이 특채의
        # 근거를 들고 있는 것이고, 특채인데 비어 있으면 위의 외래키가 통째로
        # 건너뛰어진다 — 복합 외래키는 한 칸이라도 `NULL` 이면 검사하지 않는다.
        CheckConstraint(
            f"(result = '{codes.JUDGMENT_SPECIAL}')"
            " = (special_acceptance_allowed IS NOT NULL)",
            name="ck_inspection_special_acceptance_matches_result",
        ),
        # 차 있다면 참이다. **거짓을 받으면** 그 줄은 「특채가 닫힌 사유로 특채를
        # 냈다」가 되고, 외래키는 그런 짝이 실재하므로 막지 못한다.
        CheckConstraint(
            "special_acceptance_allowed IS NOT FALSE",
            name="ck_inspection_special_acceptance_is_allowed",
        ),
        # `id` 가 이미 기본키라 행을 좁히지 않는다 — **측정 줄이 가리킬 상대**다.
        UniqueConstraint("id", "material_group", name="uq_inspection_id_material_group"),
        # **로트가 가리킬 상대.** 「불합격이 로트를 만들지 못한다」는 다른 표의
        # 칸을 보는 조건이라 CHECK 로 적을 수 없다 — 로트가 판정을 함께 들고
        # 이 쌍을 가리키면 그 줄만 보고 막을 수 있다.
        UniqueConstraint("id", "result", name="uq_inspection_id_result"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # **단계 칸은 데이터가 아니라 구조다.** 값이 언제나 같으므로 기본값을 두고
    # CHECK 가 그것을 못박는다 — 공통코드의 그룹 칸과 같은 모양이며, 사유를
    # 가리키는 복합 외래키가 이 칸을 단계 자리에 그대로 쓴다.
    inspection_stage: Mapped[str] = mapped_column(
        String(20), default=codes.STAGE_INCOMING, server_default=codes.STAGE_INCOMING
    )
    stage_group: Mapped[str] = mapped_column(
        String(20), default=codes.INSP_STAGE, server_default=codes.INSP_STAGE
    )

    item_id: Mapped[int] = mapped_column(Integer)
    item_type: Mapped[str] = mapped_column(
        String(20), default=codes.RAW_MATERIAL, server_default=codes.RAW_MATERIAL
    )
    # 품목이 아는 사실을 그대로 든다 — 위의 외래키가 둘을 묶는다.
    material_group: Mapped[str] = mapped_column(String(30))

    supplier_id: Mapped[int] = mapped_column(Integer)
    supplier_type: Mapped[str] = mapped_column(
        String(10), default=codes.SUPPLIER, server_default=codes.SUPPLIER
    )

    # **로트 번호와 같지 않을 수 있다.** 공급사가 붙여 온 번호를 그대로 적는
    # 자리이며, 우리 로트 번호는 우리가 짓는다 — 남이 지은 번호를 우리 유일키에
    # 그대로 쓰면 두 공급사가 같은 번호를 쓸 때 둘째 입고가 거부된다.
    supplier_lot_number: Mapped[str] = mapped_column(String(50))

    quantity: Mapped[float] = mapped_column(Float)

    judged_at: Mapped[datetime] = mapped_column(DateTime)
    # **판정자.** 사용자 표 없이 식별 칸 하나로 적는다.
    judged_by: Mapped[str] = mapped_column(String(50))

    result: Mapped[str] = mapped_column(String(10))

    # 합격이면 비고, 불합격·특채면 찬다 — 위의 양방향 CHECK 가 그것을 건다.
    nonconformity_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    nonconformity_group: Mapped[str] = mapped_column(
        String(20), default=codes.NC_REASON, server_default=codes.NC_REASON
    )

    # **특채인 줄에서만 차고, 차면 참이다.** 값을 나르는 칸이 아니라 외래키가
    # 특채가 열린 사유를 가리키게 하는 **자리**다 — 그래서 이 칸에 담긴 것은
    # 「이 줄이 특채이며 그 사유가 특채를 여는 사유였다」는 사실 하나뿐이다.
    special_acceptance_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class InspectionMeasurement(Base):
    """검사 한 건의 **항목별 실측값** 한 줄.

    **사람이 넣는 것은 측정값 하나뿐이다.** 품목을 고르면 자재군이 정해지고,
    자재군이 — 단계와 함께 — 항목 목록을 정하고, 항목을 고르면 규격이 딸려 온다.
    그 딸려 온 규격을 **이 줄이 박아 둔다.**

    ### 규격을 박아 두는 이유 — 파생값 금지의 그 예외다

    원칙은 「파생값은 저장하지 않는다」이고 예외는 하나다 — **「그 판정의 근거가
    되었고 밖으로 나간 값」.** 규격은 고객이 정하고 **바뀐다.** 바뀐 뒤에 옛
    검사를 열면 「측정값 12.4 · 합격」인데 지금 규격으로 재계산하면 불합격이
    나온다 — 기록이 자기모순을 일으킨다.

    그래서 **합격 여부가 아니라 그때 쓴 규격을 박는다.** 판정은 측정값과 박아 둔
    규격에서 언제나 같게 계산되므로, 파생값을 저장하지 않으면서도 판정이
    재현된다.

    ### 규격이 둘 다 비어 있는 항목은 잰 줄이 서지 않는다

    상·하한이 둘 다 `NULL` 인 항목은 **재는 항목이 아니다** — 수입 기준에서 그런
    것은 `이물` · `포장` · `성적서` 이고, 그 셋은 `nonconformity_attributes` 에서
    정확히 **계수** 코드다. 세는 것이지 재는 것이 아니므로 관리도에 오를 측정값이
    없고, 불합격은 `inspections.nonconformity_code` 로 적힌다.

    조용히 합격시키면 「아무것도 걸러 내지 않는 기준」이 되므로 **CHECK 가 막는다.**
    이 줄이 판정 시점의 규격을 스스로 들고 있어 다른 표를 보지 않고 걸린다 —
    계수 항목의 기준을 베껴 오면 두 칸이 다 비고, 그 자리에서 거부된다.

    ### 분말에 점도를 재지 않는다

    기준을 가리키는 외래키가 `(공정 × 검사항목 × 자재군)` 셋을 다 본다. 그리고
    그 자재군은 **검사가 든 자재군**이어야 한다 — 검사는 자기 품목에서 그것을
    받았으므로, 세 표가 한 줄로 묶여 **품목의 무리가 아닌 기준은 가리킬 수 없다.**
    자재군 축이 연 것을 한 겹 아래에서 닫는 자리다.
    """

    __tablename__ = "inspection_measurements"
    __table_args__ = (
        # **검사와 같은 자재군이어야 한다.** `inspection_id` 만 가리키면 이 묶음이
        # 끊기고, 그러면 분체를 받은 검사에 시트필름 기준이 붙는다.
        ForeignKeyConstraint(
            ["inspection_id", "material_group"],
            ["inspections.id", "inspections.material_group"],
            name="fk_inspection_measurement_inspection",
        ),
        # **기준이 실재함을 DB 가 보증한다.** 공정과 항목만 가리키면 자재군이
        # 풀리므로 셋을 함께 가리킨다 — 기준 표의 정체성이 그 셋이다.
        ForeignKeyConstraint(
            ["process_code", "item_code", "material_group"],
            [
                "process_inspection_standards.process_code",
                "process_inspection_standards.item_code",
                "process_inspection_standards.material_group",
            ],
            name="fk_inspection_measurement_standard",
        ),
        # **공정을 못박는 CHECK 를 두지 않는다 — 외래키가 이미 그것을 건다.**
        # 기준 표에 「자재군이 있다 ⇔ 수입」이 양방향으로 걸려 있고, 이 줄은
        # 자재군을 **반드시 들고** 기준을 가리킨다. 그래서 가리킬 수 있는 기준은
        # 자재군이 있는 줄, 곧 수입 기준뿐이다. 같은 명제를 CHECK 로 한 번 더
        # 적으면 관문 2 에서 한 자리가 남는다 — 그 대신 **테스트가 이것을
        # 이름으로 지킨다**(공정검사 기준을 가리키는 줄이 거부되는지).
        #
        # ── 값이 뜻을 갖는가 ────────────────────────────────────────────────
        # **하한이 없으므로 단독으로 건다.** 측정값에 `NaN` 이 들어가면 규격과의
        # 비교가 전부 거짓이 되어, 판정하는 쪽에서 합격도 불합격도 나오지 않는다.
        CheckConstraint(is_finite("measured_value"), name="ck_inspection_measurement_value"),
        # **규격에 `NaN` 이 들어가면 모든 측정값이 합격한다.** 서로의 순서를 보는
        # 아래 CHECK 는 그것을 막지 못한다 — `NaN > 하한` 이 참이기 때문이다.
        # 기준 표가 자기 규격 칸에 같은 것을 걸어 둔 것과 같은 이유다.
        CheckConstraint(
            f"applied_upper_spec IS NULL OR ({is_finite('applied_upper_spec')})",
            name="ck_inspection_measurement_upper_spec_is_finite",
        ),
        CheckConstraint(
            f"applied_lower_spec IS NULL OR ({is_finite('applied_lower_spec')})",
            name="ck_inspection_measurement_lower_spec_is_finite",
        ),
        # **둘 다 비지는 못한다** — 그것은 재는 항목이 아니라는 뜻이다.
        CheckConstraint(
            "applied_upper_spec IS NOT NULL OR applied_lower_spec IS NOT NULL",
            name="ck_inspection_measurement_has_a_spec",
        ),
        # 거꾸로 선 규격은 터지지 않고 **조용히 틀린 판정**을 만든다. 기준 표가
        # 같은 것을 거는데, 박아 둔 쌍이 그것을 물려받지 못할 이유가 없다.
        CheckConstraint(
            "applied_upper_spec IS NULL"
            " OR applied_lower_spec IS NULL"
            " OR applied_upper_spec > applied_lower_spec",
            name="ck_inspection_measurement_spec_order",
        ),
    )

    # **한 검사에서 같은 항목을 두 번 적지 않는다.** 두 줄이 서면 어느 값으로
    # 판정했는지 말할 수 없다. 나머지 두 칸은 기준을 가리키는 자리라 정체성에
    # 넣지 않는다 — 검사가 자재군을 정하고 단계가 공정을 정하므로, 같은
    # `(검사 × 항목)` 에 다른 값이 올 수 없다.
    inspection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_code: Mapped[str] = mapped_column(String(30), primary_key=True)

    # **기본값을 두지 않는다.** 오늘은 값이 하나뿐이지만 그것은 단계가 하나이기
    # 때문이고, 이 칸이 말하는 것은 「어느 공정의 기준을 썼는가」라는 사실이다.
    # 구조로 고정된 칸(`stage_group` 같은)과 다르다.
    process_code: Mapped[str] = mapped_column(String(30))
    material_group: Mapped[str] = mapped_column(String(30))

    measured_value: Mapped[float] = mapped_column(Float)

    # **판정 시점의 규격.** 기준이 나중에 바뀌어도 그때 그 판정은 재현된다.
    applied_upper_spec: Mapped[float | None] = mapped_column(Float, nullable=True)
    applied_lower_spec: Mapped[float | None] = mapped_column(Float, nullable=True)
