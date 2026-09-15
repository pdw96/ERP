"""공통코드 그룹 목록 — **프로그램이 아는 이름**.

그룹은 전부 Major다. 프로그램이 이름으로 부르므로 화면에서 하나도 더할 수
없고 지울 수 없다. 갈리는 것은 그룹이 아니라 **그 안의 값**이고, 그래서 아래
목록이 갖는 열은 「값이 늘 수 있는가」다.

가르는 잣대는 하나 — **프로그램이 그 값을 보고 분기하는가.** 분기한다면 값을
더할 때 그것을 처리할 코드가 없으므로 화면에서 늘릴 수 없다: 「수정 불가」의
이유가 규칙이 아니라 구조다. 분기하지 않고 세기만 한다면 얼마든지 늘어도
아무 코드도 고장 나지 않는다.

**값은 여기 없다.** 값은 시드 SQL 에 있다 — 사람이 읽고 고치는 표이고, 코드를
몰라도 한 줄 추가로 늘릴 수 있어야 하기 때문이다. 여기 있는 것은 이름뿐이며,
둘이 어긋나지 않는지는 테스트가 지킨다.
"""

from typing import NamedTuple


class CodeGroupDef(NamedTuple):
    """공통코드 그룹 하나의 정의."""

    group_code: str
    name: str
    # 값이 늘 수 있는가. False 면 값마다 프로그램이 분기한다.
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

# ── 값이 늘 수 있는 그룹 여덟 — 세기만 한다 ────────────────────────────────
NC_REASON = "NC_REASON"
PO_CLOSE = "PO_CLOSE"
SP_REASON = "SP_REASON"
ADJ_REASON = "ADJ_REASON"
PROCESS = "PROCESS"
INSP_ITEM = "INSP_ITEM"
DEPT = "DEPT"
UOM = "UOM"


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
        "계량 14는 검사 항목에서 따라 나오고 손으로 두는 것은 계수 4뿐이다.",
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
    ),
    CodeGroupDef(DEPT, "부서", False, "조직의 사실. 교차 실사 기록이 이것을 요구한다."),
    CodeGroupDef(UOM, "단위", False, "kg · L · EA · m² — 늘어도 아무것도 고장 나지 않는다."),
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
