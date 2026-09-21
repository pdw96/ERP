"""공통코드 그룹 목록 — **프로그램이 아는 이름**.

그룹은 전부 Major다. 프로그램이 이름으로 부르므로 화면에서 하나도 더할 수
없고 지울 수 없다. 갈리는 것은 그룹이 아니라 **그 안의 값**이고, 그래서 아래
목록이 갖는 열이 `value_fixed` 다 — **참이면 값이 고정**이고, 거짓이면 늘 수 있다.

가르는 잣대는 하나 — **프로그램이 그 값을 보고 분기하는가.** 분기한다면 값을
더할 때 그것을 처리할 코드가 없으므로 화면에서 늘릴 수 없다: 「수정 불가」의
이유가 규칙이 아니라 구조다. 분기하지 않고 세기만 한다면 얼마든지 늘어도
아무 코드도 고장 나지 않는다.

**늘 수 있는 그룹의 값은 여기 없다.** 그 값은 시드 SQL 에 있다 — 사람이 읽고
고치는 표이고, 코드를 몰라도 한 줄 추가로 늘릴 수 있어야 하기 때문이다. 여기 있는
것은 그룹 이름과, **고정된 그룹의 값**뿐이며(아래 「값이 고정된 그룹의 값」), 시드와
어긋나지 않는지는 테스트가 지킨다.
"""

from typing import NamedTuple


class CodeGroupDef(NamedTuple):
    """공통코드 그룹 하나의 정의."""

    group_code: str
    name: str
    # 값이 고정인가. **참이면** 값마다 프로그램이 분기하므로 화면에서 늘릴 수 없다.
    value_fixed: bool
    description: str


# ── 값이 고정된 그룹 열다섯 — 프로그램이 분기한다 ──────────────────────────
WAREHOUSE = "WAREHOUSE"
STOCK_TYPE = "STOCK_TYPE"
ITEM_TYPE = "ITEM_TYPE"
TXN_TYPE = "TXN_TYPE"
INSP_STAGE = "INSP_STAGE"
ORDER_TYPE = "ORDER_TYPE"
ORDER_MODE = "ORDER_MODE"
SHIP_TYPE = "SHIP_TYPE"
ITEM_PHASE = "ITEM_PHASE"
MEAS_KIND = "MEAS_KIND"
SIGMA_SRC = "SIGMA_SRC"
WE_RULE = "WE_RULE"
SHIFT = "SHIFT"
SETTLE_TYPE = "SETTLE_TYPE"
RISK_STATUS = "RISK_STATUS"

# ── 값이 늘 수 있는 그룹 아홉 — 세기만 한다 ────────────────────────────────
NC_REASON = "NC_REASON"
PO_CLOSE = "PO_CLOSE"
SP_REASON = "SP_REASON"
ADJ_REASON = "ADJ_REASON"
PROCESS = "PROCESS"
INSP_ITEM = "INSP_ITEM"
DEPT = "DEPT"
UOM = "UOM"
MATERIAL_GROUP = "MATERIAL_GROUP"


CODE_GROUPS: tuple[CodeGroupDef, ...] = (
    CodeGroupDef(WAREHOUSE, "창고", True, "흐름의 구간이다. 창고를 더하면 도해가 바뀐다."),
    CodeGroupDef(STOCK_TYPE, "재고구분", True, "출하 가능 여부를 가른다."),
    CodeGroupDef(ITEM_TYPE, "품목유형", True, "BOM 전개와 검사 경로가 갈린다."),
    CodeGroupDef(TXN_TYPE, "수불유형", True, "부호와 재고 반영이 유형마다 다르다."),
    CodeGroupDef(
        INSP_STAGE,
        "검사단계",
        True,
        "단계마다 다른 일을 한다 — IQC 는 자재 로트를, FQC 는 완제품 로트를 만든다.",
    ),
    CodeGroupDef(ORDER_TYPE, "오더유형", True, "2단 BOM 전개의 두 자리."),
    CodeGroupDef(ORDER_MODE, "오더성격", True, "양산과 시양산은 오더유형과 다른 축이다."),
    CodeGroupDef(SHIP_TYPE, "출하유형", True, "보이는 재고가 갈린다."),
    CodeGroupDef(ITEM_PHASE, "품목단계", True, "게이트와 지표가 다르다 (Ppk 1.67 / Cpk 1.33)."),
    CodeGroupDef(MEAS_KIND, "항목유형", True, "계량만 관리도에 오른다."),
    CodeGroupDef(
        SIGMA_SRC, "σ출처", True, "Cpk 를 낼지 말지를 정한다 — 「미정」이면 숫자를 내지 않는다."
    ),
    CodeGroupDef(
        WE_RULE, "판정규칙", True, "규칙마다 계산이 다르고, 검사 기준에서 켜고 끄는 단위다."
    ),
    CodeGroupDef(SHIFT, "근무형태", True, "실사 창과 경과 시간 계산이 여기서 나온다."),
    CodeGroupDef(
        SETTLE_TYPE, "반품정산", True, "대물은 물건이 돌아가고 대금은 전산상 소멸한다."
    ),
    CodeGroupDef(
        RISK_STATUS,
        "경보상태",
        True,
        "경보 층은 이 저장소에 없지만 값이 셋뿐이라 미리 둔다 — 돌아올 때 그룹을 새로 "
        "만드는 것보다 낫다. 빼도 다른 결정에 얽히지 않는다.",
    ),
    CodeGroupDef(
        NC_REASON,
        "불합격사유",
        False,
        "열아홉 중 열여덟이 검사 항목을 가리킨다. 가리킬 항목이 없는 것은 IQ-EXP 하나다.",
    ),
    CodeGroupDef(
        PO_CLOSE, "미납종결사유", False, "누구 탓인가와 그 물건이 아직 필요한가를 센다."
    ),
    CodeGroupDef(SP_REASON, "특채사유", False, "불합격인데 쓰기로 한 결정의 이유."),
    CodeGroupDef(
        ADJ_REASON,
        "조정사유",
        False,
        "실제로 조정을 내 보아야 목록이 나온다 — 지금 비어 있는 것이 맞다.",
    ),
    CodeGroupDef(
        PROCESS,
        "공정",
        False,
        "검사 항목을 고르는 라벨이다. 설비와 라우팅이 들어오면 고정 쪽으로 옮겨간다.",
    ),
    CodeGroupDef(
        INSP_ITEM,
        "검사항목",
        False,
        "이름만 여기 있고 규격·중심선·경고선·σ·경시변화는 (공정 × 항목) 표에 있다.",
    ),  # 설계도의 공정표는 18이고, 이 저장소의 값은 16이다 — 그 유도는 시드 주석에 있다.
    CodeGroupDef(DEPT, "부서", False, "조직의 사실. 교차 실사 기록이 이것을 요구한다."),
    CodeGroupDef(UOM, "단위", False, "kg · L · EA · m² — 늘어도 아무것도 고장 나지 않는다."),
    CodeGroupDef(
        MATERIAL_GROUP,
        "자재군",
        False,
        "수입 검사 기준이 걸리는 축이다 — 분말에 점도를, 라이너에 입도를 재라고 "
        "내밀지 않기 위해 있다. 무리가 늘어도 프로그램은 분기하지 않고 주소로만 쓴다.",
    ),
)

GROUP_CODES: tuple[str, ...] = tuple(group.group_code for group in CODE_GROUPS)


# ── 값이 고정된 그룹의 값 ───────────────────────────────────────────────────
# 프로그램이 이 값을 보고 분기하므로 **여기에도 적고 CHECK 로 박는다.** 값이
# 가변인 그룹(공정 · 단위 …)은 반대로 여기 적지 않고 복합 외래키로 공통코드를
# 가리킨다 — 파이썬 상수에서 구워 CHECK 로 박으면 「늘 수 있다」고 선언한
# 그룹이 실제로는 얼어붙기 때문이다.

FINISHED_GOODS = "완제품"
SEMI_FINISHED = "반제품"
RAW_MATERIAL = "원자재"
ITEM_TYPES = (FINISHED_GOODS, SEMI_FINISHED, RAW_MATERIAL)

# 품목 코드의 접두. **접두는 유형과 유일성만 맡는다** — 공정을 담지 않는다.
# 담으면 공정이 바뀔 때 코드를 바꿔야 하고, 코드는 바뀌지 않는 것이어야 한다.
ITEM_CODE_PREFIXES: dict[str, str] = {
    FINISHED_GOODS: "FG-",
    SEMI_FINISHED: "SF-",
    RAW_MATERIAL: "RM-",
}

PHASE_INITIAL = "초기"
PHASE_MASS_PRODUCTION = "양산"
ITEM_PHASES = (PHASE_INITIAL, PHASE_MASS_PRODUCTION)

# 2단 고정 BOM. 1단 = 완제품 ← 반제품 · 2단 = 반제품 ← 원자재.
BOM_LEVELS = (1, 2)
BOM_LEVEL_TYPES: dict[int, tuple[str, str]] = {
    1: (FINISHED_GOODS, SEMI_FINISHED),
    2: (SEMI_FINISHED, RAW_MATERIAL),
}


# ── 수불유형의 총량 영향 ────────────────────────────────────────────────────
# 「불변」은 재고구분 대체다 — 총량은 그대로이고 양품재고만 준다. 「기준점」은
# 전기이월이며, 잔량은 그 줄부터 더한다.
EFFECT_INCREASE = "증가"
EFFECT_DECREASE = "감소"
EFFECT_BOTH = "양방향"
EFFECT_NONE = "불변"
EFFECT_BASELINE = "기준점"
TOTAL_EFFECTS = (
    EFFECT_INCREASE,
    EFFECT_DECREASE,
    EFFECT_BOTH,
    EFFECT_NONE,
    EFFECT_BASELINE,
)

# ── 불합격 처분 ─────────────────────────────────────────────────────────────
# 「고칠 수 있는가」가 처분을 가른다 — 고칠 수 없는 것(이물 · 접착력 · 배합비)은
# 폐기, 쓸 수는 있는 것(치수 · 광택 · 색차 · 점도)은 등급 하향이나 특채,
# 물건이 아니라 조건이 틀린 것(온도 · 속도 · 두께)은 재작업이다.
DISPOSITIONS = ("반품", "환불", "재작업", "폐기", "등급 하향")

# ── 검사 항목의 성질 ────────────────────────────────────────────────────────
MEASURED_KIND = "계량"
COUNTED_KIND = "계수"
MEASURE_KINDS = (MEASURED_KIND, COUNTED_KIND)

# ── 미납 종결 ───────────────────────────────────────────────────────────────
# 성적 축이 **비어 있으면 공급사 성적에 잡히지 않는다.** 따로 「반영 여부」 칸을
# 두면 둘이 어긋날 수 있고, 어긋나면 단종처럼 예외인 줄에서 어긋난다.
SCORECARD_AXES = ("수량 준수율", "납기 준수율", "공급 가능성")
REORDER_DEFAULTS = ("필요", "불필요", "건별")
RESPONSIBILITIES = ("공급사", "자사")


# ── 거래처 ──────────────────────────────────────────────────────────────────
# 공급사(반품 · 환불)와 고객사(수주 · 출하). 없으면 구간 1과 5가 성립하지 않는다.
SUPPLIER = "공급사"
CUSTOMER = "고객사"
PARTNER_TYPES = (SUPPLIER, CUSTOMER)


# ── σ 와 세 개의 선 ─────────────────────────────────────────────────────────
# σ 출처가 없으면 **화면의 Cpk 가 진짜인지 자리표시자인지 아무도 모른다.**
# 「미정」이면 숫자를 내지 않는다 — 규격에서 뽑은 σ 는 어떤 계수를 쓰든 Cpk 를
# 그 계수의 역수로 못박기 때문이다.
SIGMA_UNDECIDED = "미정"
SIGMA_ASSUMED = "임의"
SIGMA_OBSERVED = "실측"
SIGMA_SOURCES = (SIGMA_UNDECIDED, SIGMA_ASSUMED, SIGMA_OBSERVED)

# 경고선의 기본 계수. 규격에서 긋는 **사내 기준**이며 사내만 본다 — 더 이르게
# 알고 싶으면 조여도 고객에게 알릴 일이 아니다. 항목마다 다르게 둘 수 있도록
# 상수가 아니라 칸으로 만든다.
DEFAULT_WARNING_RATIO = 0.70


# ── 재고가 사는 곳 ──────────────────────────────────────────────────────────
WAREHOUSE_RAW = "원재료"
WAREHOUSE_PRODUCTION = "생산"
WAREHOUSE_FINISHED = "제품"
WAREHOUSES = (WAREHOUSE_RAW, WAREHOUSE_PRODUCTION, WAREHOUSE_FINISHED)

# 제품창고 **안에서** 갈린다. 불합격품은 재고가 되지 않으므로 앞의 두 창고에는
# 불량품이 없다 — OQC 에서 떨어져 양불이동된 것만 불량품이 된다.
STOCK_GOOD = "양품"
STOCK_DEFECTIVE = "불량품"
STOCK_TYPES = (STOCK_GOOD, STOCK_DEFECTIVE)

# 어느 창고가 어느 품목을 담는가. 생산창고만 셋 다 담는다 — 투입 대기 자재와
# 반제품과 완제품이 함께 있기 때문이다.
WAREHOUSE_ITEM_TYPES: dict[str, tuple[str, ...]] = {
    WAREHOUSE_RAW: (RAW_MATERIAL,),
    WAREHOUSE_PRODUCTION: (RAW_MATERIAL, SEMI_FINISHED, FINISHED_GOODS),
    WAREHOUSE_FINISHED: (FINISHED_GOODS,),
}

# ── 로트 번호의 출처 ────────────────────────────────────────────────────────
# 원칙 ① — 재고 로트는 언제나 합격 후에 생긴다. **번호의 출처만 다르다.**
LOT_FROM_SUPPLIER = "공급사"
LOT_FROM_OWN = "자사"
LOT_ORIGINS = (LOT_FROM_SUPPLIER, LOT_FROM_OWN)

# 자재는 사서 들어오고 반제품과 완제품은 만들어 나온다.
LOT_ORIGIN_ITEM_TYPES: dict[str, tuple[str, ...]] = {
    LOT_FROM_SUPPLIER: (RAW_MATERIAL,),
    LOT_FROM_OWN: (SEMI_FINISHED, FINISHED_GOODS),
}


# ── 검사 단계가 어느 공정의 기준을 쓰는가 ──────────────────────────────────
# 품목의 `process` 는 그 품목이 **산출되는** 공정이고, 검사 기준을 실제로
# 고르는 것은 **단계**다. 완제품은 적층경화(FQC)와 출하(OQC) 두 번 검사받는데
# 품목이 가진 공정은 하나뿐이므로, 그 대응을 여기 둔다.
#
# **재검사는 빠져 있다.** 원 단계의 기준을 다시 쓰되 경시 변화 항목만 보므로
# 단계 하나에 공정 하나가 붙지 않는다.
STAGE_INCOMING = "IQC"
STAGE_PROCESSES: dict[str, tuple[str, ...]] = {
    STAGE_INCOMING: ("수입",),
    "IPQC": ("배합", "코팅"),
    "FQC": ("적층경화",),
    "OQC": ("출하",),
}
RETEST_STAGE = "재검사"


# ── 검사의 판정 ─────────────────────────────────────────────────────────────
# **로트를 만드는 값이다.** 원칙 ① 이 「재고 로트는 합격 후에 생긴다」이고 예외는
# 특채 하나이므로, 이 셋은 프로그램이 분기하는 값이다.
#
# **공통코드 그룹으로 두지 않는다.** 그룹을 더하는 것은 앵커볼트를 건드리는
# 일인데, 이 셋은 늘지 않는다 — 넷째 판정이 생기면 그것은 코드값이 느는 것이
# 아니라 원칙 ① 이 바뀌는 것이다. 처분(`DISPOSITIONS`)을 여기 둔 것과 같은
# 자리이며, CHECK 가 이것을 박는다.
JUDGMENT_PASSED = "합격"
JUDGMENT_FAILED = "불합격"
JUDGMENT_SPECIAL = "특채"
JUDGMENTS = (JUDGMENT_PASSED, JUDGMENT_FAILED, JUDGMENT_SPECIAL)

# ── 자재군이 붙는 공정 ──────────────────────────────────────────────────────
# **자재군은 원자재를 보는 검사에만 붙는다.** 반제품과 완제품에는 자재군이 없다 —
# 만들어져 나온 것이라 「무슨 자재인가」를 물을 수 없기 때문이다.
#
# 원자재를 보는 것은 IQC 하나뿐이므로 위의 대응표에서 그대로 끌어 쓴다. 여기에
# 따로 적으면 목록이 두 벌이 되고, 두 벌이면 반드시 갈린다.
MATERIAL_GROUPED_PROCESSES: tuple[str, ...] = STAGE_PROCESSES[STAGE_INCOMING]
