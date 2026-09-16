"""품질 기준정보 — 공정별 검사 기준.

한 항목이 값 여섯을 갖는다 — 규격(상·하한) · 중심선 · 경고선 계수 · σ ·
σ 출처 · 경시 변화 여부. 품목 코드를 고르면 그 품목의 공정이 정해지고, 공정이
항목 목록을 정하고, 항목을 고르면 여섯 값이 딸려 온다. **사람이 넣는 것은
측정값 하나뿐이다.**
"""

from sqlalchemy import Boolean, CheckConstraint, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference, is_finite


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class ProcessInspectionStandard(Base):
    """(공정 × 검사항목) 한 줄.

    **σ 를 비워 둔다.** 규격에서 뽑은 σ 는 어떤 계수를 쓰든 Cpk 를 그 계수의
    역수로 못박아, 어떤 공정에서든 같은 숫자가 나온다. 경고선과 WE 규칙 4 는
    σ 없이 그대로 도므로 비워 두는 편이 안전하다 — **없는 값을 지어내면
    화면에서는 있는 것처럼 보인다.**
    """

    __tablename__ = "process_inspection_standards"
    __table_args__ = (
        *code_reference(
            group_column="process_group",
            code_column="process_code",
            group_code=codes.PROCESS,
            name="inspection_standard_process",
        ),
        *code_reference(
            group_column="item_group",
            code_column="item_code",
            group_code=codes.INSP_ITEM,
            name="inspection_standard_item",
        ),
        CheckConstraint(
            f"sigma_source IN ({_quoted(codes.SIGMA_SOURCES)})",
            name="ck_inspection_standard_sigma_source",
        ),
        # **양방향이다.** σ 가 있는데 출처가 「미정」이면 그 숫자가 어디서 왔는지
        # 아무도 모르고, 출처가 「실측」인데 σ 가 없으면 잰 적 없는 것을 쟀다고
        # 적은 것이다. 한쪽만 걸면 다른 쪽으로 새는 줄이 선다.
        CheckConstraint(
            f"(sigma IS NULL) = (sigma_source = '{codes.SIGMA_UNDECIDED}')",
            name="ck_inspection_standard_sigma_matches_source",
        ),
        CheckConstraint(
            f"sigma IS NULL OR (sigma > 0 AND {is_finite('sigma')})",
            name="ck_inspection_standard_sigma",
        ),
        # 경고선은 **규격 안쪽에** 긋는 선이다. 1 이면 규격과 겹쳐 「규격에
        # 가까워졌는가」를 미리 말하지 못하고, 0 이하면 중심선 반대편에 선다.
        CheckConstraint(
            "warning_ratio > 0 AND warning_ratio < 1",
            name="ck_inspection_standard_warning_ratio",
        ),
        # **규격에 `NaN` 이 들어가면 모든 측정값이 합격한다.**
        #
        # 아래의 순서 CHECK 는 이것을 막지 못한다 — `NaN > 하한` 이 참이고
        # `중심선 <= NaN` 도 참이라 줄이 그대로 선다. 그리고 판정하는 쪽에서
        # `측정값 <= 상한` 이 **언제나 참**이 되어, 규격이 있는 것처럼 보이는데
        # 아무것도 걸러 내지 않는 기준이 된다. 불합격이 한 건도 나지 않는 공정은
        # 정상으로 보인다.
        CheckConstraint(
            f"upper_spec_limit IS NULL OR ({is_finite('upper_spec_limit')})",
            name="ck_inspection_standard_upper_spec_limit_is_finite",
        ),
        CheckConstraint(
            f"lower_spec_limit IS NULL OR ({is_finite('lower_spec_limit')})",
            name="ck_inspection_standard_lower_spec_limit_is_finite",
        ),
        CheckConstraint(
            f"center_line IS NULL OR ({is_finite('center_line')})",
            name="ck_inspection_standard_center_line_is_finite",
        ),
        CheckConstraint(
            "upper_spec_limit IS NULL"
            " OR lower_spec_limit IS NULL"
            " OR upper_spec_limit > lower_spec_limit",
            name="ck_inspection_standard_spec_order",
        ),
        # 중심선이 규격 밖에 있으면 「정상으로 돌아가는 목표」가 불합격 구간이다.
        CheckConstraint(
            "center_line IS NULL"
            " OR ((upper_spec_limit IS NULL OR center_line <= upper_spec_limit)"
            " AND (lower_spec_limit IS NULL OR center_line >= lower_spec_limit))",
            name="ck_inspection_standard_center_within_spec",
        ),
    )

    # **이 PK 는 품목을 가리지 못한다 — 아직.** 「수입」 기준 여덟이 원자재
    # 열다섯 전부에 똑같이 걸린다. 자재는 한 덩어리가 아니고 재고단위가 그것을
    # 말한다(KG 아홉 · L 둘 · M2 넷) — 분말에 점도를, 라이너에 입도를 재라고
    # 내미는 셈이다.
    #
    # **2단계 착공에서 정해졌다 — 자재군을 둔다.** 품목 축을 더하면 원자재 15 ×
    # 검사항목만큼의 실측값을 누군가 정해야 하고, 그 값이 없으면 빈 기준정보가
    # 된다. 자재군은 재고단위가 이미 경계를 말하고 있어 지어낼 값이 없다.
    #
    # **아직 이 표는 바뀌지 않았다.** 자재군 축이 PK 에 붙는 것은 마이그레이션이
    # 있는 조각의 일이다 — 이미 심긴 표라 재시드가 닿지 않는다. 초안은
    # `docs/schema-2단계.md` 15번에 있다.
    process_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    process_group: Mapped[str] = mapped_column(
        String(20), default=codes.PROCESS, server_default=codes.PROCESS
    )
    item_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    item_group: Mapped[str] = mapped_column(
        String(20), default=codes.INSP_ITEM, server_default=codes.INSP_ITEM
    )

    # 규격은 고객이 정한다 — 지금은 임의 설정이다.
    upper_spec_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    lower_spec_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_line: Mapped[float | None] = mapped_column(Float, nullable=True)

    warning_ratio: Mapped[float] = mapped_column(
        Float, default=codes.DEFAULT_WARNING_RATIO, server_default="0.70"
    )
    sigma: Mapped[float | None] = mapped_column(Float, nullable=True)
    sigma_source: Mapped[str] = mapped_column(
        String(10), default=codes.SIGMA_UNDECIDED, server_default=codes.SIGMA_UNDECIDED
    )

    # 「시간이 이 값을 바꿀 수 있는가.」 만료 재검사가 다시 보는 항목은 이 칸이
    # 켜진 것뿐이다 — 재검사는 시간이 바꾸는 것만 본다.
    time_variant: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # mm · cP · ΔE 처럼 재는 단위. 재고 단위(`UOM`)와 다른 축이라 공통코드를
    # 가리키지 않는다 — 섞으면 「킬로그램으로 재는 색차」가 적힌다.
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
