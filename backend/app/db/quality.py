"""품질 기준정보 — 공정별 검사 기준.

한 항목이 **값 칸 여덟**을 갖는다 — 규격 상·하한 · 중심선 · 경고선 계수 · σ ·
σ 출처 · 경시 변화 여부 · 단위(마이그레이션의 `_VALUE_COLUMNS` 가 같은 여덟을
부른다). 품목 코드를 고르면 그 품목의 공정이 정해지고, **공정이 — 수입이면
자재군까지 — 항목 목록을 정하고**, 항목을 고르면 그 여덟이 딸려 온다.
**사람이 넣는 것은 측정값 하나뿐이다.**
"""

from sqlalchemy import Boolean, CheckConstraint, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core import codes
from app.db.base import Base
from app.db.constraints import code_reference, is_finite


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class ProcessInspectionStandard(Base):
    """(공정 × 검사항목 × 자재군) 한 줄 — 자재군은 수입에서만 찬다.

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
        *code_reference(
            group_column="material_group_group",
            code_column="material_group",
            group_code=codes.MATERIAL_GROUP,
            name="inspection_standard_material_group",
        ),
        # **이 줄의 정체성이다.** 자재군이 `NULL` 인 줄(공정검사)은 (공정 ×
        # 검사항목)으로, 자재군이 있는 줄(수입)은 셋으로 갈린다.
        #
        # `NULLS NOT DISTINCT` 가 없으면 PostgreSQL 은 `NULL` 을 서로 다른 값으로
        # 보아 **같은 (공정 × 검사항목)이 몇 줄이든 선다** — 「배합 · 공정온도」가
        # 둘이 되면 어느 기준으로 판정했는지 말할 수 없다. PostgreSQL 15 부터
        # 쓸 수 있고 우리는 16 이다.
        UniqueConstraint(
            "process_code",
            "item_code",
            "material_group",
            name="uq_inspection_standard",
            postgresql_nulls_not_distinct=True,
        ),
        # **행을 좁히지 않는다** — 위의 셋이 이미 유일하므로 넷째를 더해도 같은
        # 줄이다. **측정 줄이 단위를 가리킬 상대**를 만드는 것이 목적이고,
        # 그러면 가리키는 줄이 있는 동안 이 칸을 바꿀 수 없게 된다
        # (`inspection_measurements` 의 `fk_inspection_measurement_unit`).
        UniqueConstraint(
            "process_code",
            "item_code",
            "material_group",
            "unit",
            name="uq_inspection_standard_unit",
            postgresql_nulls_not_distinct=True,
        ),
        # **양방향이다.** 수입인데 자재군이 없으면 기준 여덟이 원자재 열다섯
        # 전부에 걸리던 옛 자리로 돌아가고, 수입이 아닌데 자재군이 있으면
        # 반제품·완제품 기준에 「무슨 자재인가」가 적힌 것이다.
        CheckConstraint(
            f"(process_code IN ({_quoted(codes.MATERIAL_GROUPED_PROCESSES)}))"
            " = (material_group IS NOT NULL)",
            name="ck_inspection_standard_material_group_matches_process",
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

    # **대리키를 쓰는 이유는 자재군이 비어 있을 수 있기 때문이다.** 이 줄의
    # 정체성은 (공정 × 검사항목 × 자재군)이지만 PostgreSQL 의 기본키는 `NULL`
    # 을 받지 않는다. 공정검사 줄에 「해당없음」 같은 값을 채우면 그것은 빈
    # 기준정보이고, 화면에 뜨는 순간 진짜로 보인다. 그래서 자리만 맡는 `id` 를
    # 두고 **정체성은 위의 유일키가 말한다.**
    id: Mapped[int] = mapped_column(primary_key=True)

    process_code: Mapped[str] = mapped_column(String(30))
    process_group: Mapped[str] = mapped_column(
        String(20), default=codes.PROCESS, server_default=codes.PROCESS
    )
    item_code: Mapped[str] = mapped_column(String(30))
    item_group: Mapped[str] = mapped_column(
        String(20), default=codes.INSP_ITEM, server_default=codes.INSP_ITEM
    )

    # **자재군 — 수입 기준이 품목을 가리게 하는 축.** 없던 시절에는 「수입」 기준
    # 여덟이 원자재 열다섯 전부에 똑같이 걸렸다: 분말에 점도를, 라이너에 입도를
    # 재라고 내미는 셈이었다.
    #
    # 품목 축이 아니라 자재군인 이유는, 품목 축을 더하면 원자재 15 × 검사항목
    # 만큼의 실측값을 누군가 정해야 하고 그 값이 지금 없기 때문이다. 자재군은
    # **품목 시드가 이미 적어 둔 구분**이다 — 지어낸 축이 아니다
    # (`seed_data/03_items.sql` 의 `material_group` 열. 재고단위는 그 경계를
    # 반만 말하므로 근거는 단위가 아니라 그 열이다).
    #
    # **공정검사 줄에서는 비어 있다.** 반제품과 완제품에는 자재군이 없다.
    material_group: Mapped[str | None] = mapped_column(String(30), nullable=True)
    material_group_group: Mapped[str] = mapped_column(
        String(20), default=codes.MATERIAL_GROUP, server_default=codes.MATERIAL_GROUP
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
