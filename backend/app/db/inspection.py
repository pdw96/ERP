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
