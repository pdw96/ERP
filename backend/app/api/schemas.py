"""요청과 응답의 모양 — **검증은 pydantic 한 벌로 한다.**

`app/services/` 의 데이터클래스와 칸이 겹쳐 보이지만 둘은 다른 것을
맡는다. 여기 있는 것은 **밖에서 들어온 것을 못 믿는 층**이라 타입과 범위를 보고,
서비스 쪽은 이미 믿을 수 있는 값으로 업무를 한다. 경계를 하나로 합치면 HTTP 를
모르는 자리에서 HTTP 의 사정을 알게 된다.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.core import codes
from app.db.constraints import blank_characters
from app.services.incoming import Refusal
from app.services.returns import ReturnRefusal

# **데이터베이스가 깎는 글자와 같은 목록이다.** 두 벌로 적지 않는다 —
# `app/db/constraints.py` 가 SQL 쪽 형태를 들고, 여기서는 그것을 푼 것을 쓴다.
_BLANK = blank_characters()


def _present(value: str) -> str:
    """**눈에는 비어 보이는데 비어 있지 않은 값**을 여기서 돌려보낸다.

    `min_length=1` 은 길이만 본다. 공백 한 칸 · 탭 · 전각 공백(U+3000)은 그것을
    통과하고, 그 다음에 기다리는 것은 `is_present()` CHECK 다 — **경계가 놓치면
    422 가 아니라 500 이 나가고** 검사원은 제약 이름을 본다. 「왜 막혔는지 모르는
    실패」가 정확히 이렇게 난다.
    """
    if not value.strip(_BLANK):
        raise ValueError("공백만으로 이루어진 값은 받지 않는다")
    # **NUL 은 PostgreSQL 의 `text` 에 들지 못한다**(Codex 리뷰, 3단계 조각 2). JSON 은
    # `\u0000` 을 실어 올 수 있고, 경계가 놓치면 드라이버가 넣는 자리에서 거부해 500 이 된다.
    if "\x00" in value:
        raise ValueError("NUL 글자는 받지 않는다")
    return value


Present = Annotated[str, AfterValidator(_present)]


# **모르는 칸은 받지 않는다.** 기본값(무시)으로 두면 `"specialAcceptance"` 같은
# 오타가 **201 로 성공하면서** 특채를 잃는다 — 받으려던 자재가 로트 없이 끝나고,
# 부르는 쪽은 자기가 보낸 것이 반영됐다고 읽는다. 뒤에 좁히는 것은 그 자체가
# 파괴적 변경이라, 정할 수 있는 때는 소비자가 붙기 전인 지금뿐이다.
_ONLY_THE_FIELDS_WE_NAME = ConfigDict(extra="forbid")


class MeasurementIn(BaseModel):
    """검사원이 적은 실측값 하나."""

    model_config = _ONLY_THE_FIELDS_WE_NAME

    item_code: Present = Field(min_length=1, max_length=30)
    # **`allow_inf_nan=False` 가 여기서도 선다.** JSON 은 `NaN` 을 실어 보낼 수
    # 있고, 들어오면 규격과의 비교가 전부 거짓이 되어 합격도 불합격도 나오지
    # 않는다. 데이터베이스도 같은 것을 막지만 거기서 나오는 말은 제약 이름이다.
    value: float = Field(allow_inf_nan=False)


class InspectionIn(BaseModel):
    """수입검사 한 건."""

    model_config = _ONLY_THE_FIELDS_WE_NAME

    item_code: Present = Field(min_length=1, max_length=50)
    supplier_code: Present = Field(min_length=1, max_length=20)
    supplier_lot_number: Present = Field(min_length=1, max_length=50)
    quantity: float = Field(ge=0, allow_inf_nan=False)
    judged_by: Present = Field(min_length=1, max_length=50)
    received_date: date
    measurements: list[MeasurementIn] = Field(default_factory=list)
    # 세는 항목에서 **사람이 잡은** 결함. 계산은 이것을 보지 못한다.
    nonconformity_code: Present | None = Field(default=None, max_length=30)
    # 불합격인데 쓰기로 한 결정. 사람만 낼 수 있다.
    special_acceptance: bool = False


class InspectionOut(BaseModel):
    """판정이 끝난 뒤 남은 것.

    **로트 번호를 돌려준다.** 창고 라벨에 찍히는 번호이고, 부르는 쪽이 그것을
    다시 물어보게 하면 한 사실을 두 번 읽게 된다.
    """

    # **자동 증가 키를 돌려주는 이유를 적는다.** 「부르는 쪽 없는 칸을 미리 두지
    # 않는다」가 NC-80 에서 `expiry_date` 를 거절한 규칙이고, 이 셋은 그 규칙을
    # 지나는 값이어야 한다(감사 ⑫ NC-137).
    #
    # - `inspection_id` — 검사에는 다른 손잡이가 없다. 반품(`POST /purchase-returns`)이
    #   **그 건을 가리키는 값**이고, 불합격에도 남는다(로트는 서지 않는다)
    # - `lot_id` — 라벨에 찍히는 것은 `lot_number` 이고, 그 번호는 **품목 안에서는
    #   유일하다**(`uq_lot_item_number`). 그러므로 부르는 쪽은 자기가 보낸
    #   `item_code` 와 돌려받은 `lot_number` 로도 로트를 가리킬 수 있고, `lot_id`
    #   는 **그 짝을 다시 맞추지 않고 응답 하나로 닫게 하는** 값이다. 원장 줄이
    #   가리키는 것도 이것이다
    # - `ledger_entry_id` — 「로트는 생겼는데 원장 줄이 없는」 상태가 없다는 것을
    #   부르는 쪽이 확인할 자리다. **주소로서 더해 주는 것은 오늘 없다** —
    #   `uq_lot_inspection` 과 구매입고의 부분 유일 인덱스 때문에 `inspection_id`
    #   하나로 로트도 그 입고 줄도 이미 결정되기 때문이다. 읽는 경로가 없어 부르는
    #   쪽이 그것을 **계산할 수는 없다**는 것이 이 칸이 서 있는 이유다
    #
    # **처음 적은 근거 둘이 거짓이었다**(감사 ⑯ NC-159) — 「`lot_number` 에 유일
    # 제약이 없다」와 「원장 줄에 업무 키가 아예 없다」. 적힌 대로 읽은 소비자는
    # **안정된 업무 키를 버리고 대리키에 붙는다.**
    #
    # **읽는 엔드포인트가 서는 날 이 셋이 그 경로의 열쇠가 된다.** 그때까지는
    # 위가 그 쓰임이다. 빼는 것은 필드 삭제이지만 **지금은 파괴적 변경이 아니다**
    # — 읽는 엔드포인트가 서기 전까지 계약을 좁히는 것이 자유롭다고 `app.py` 의
    # 판 정책이 적고, 그 둘이 한 말이어야 한다(NC-159 가 갈린 자리로 냈다).
    inspection_id: int
    # **값 집합을 스펙에 적는다.** 자유 문자열로 두면 소비자가 「합격」을
    # **문서화되지 않은 채** 하드코딩해야 하고, 관문 2 가 값을 늘려도 그것이
    # 파괴적 변경으로 취급될 근거가 없다. 목록은 `codes.JUDGMENTS` 한 벌에서
    # 끌어온다 — 여기 다시 적으면 두 벌이 되고, 두 벌은 갈린다.
    result: str = Field(json_schema_extra={"enum": list(codes.JUDGMENTS)})
    nonconformity_code: str | None
    lot_id: int | None
    lot_number: str | None
    ledger_entry_id: int | None


# **`integer` 칸의 끝.** 표의 기본키는 PostgreSQL `integer` 라, 그보다 큰 수를 들고
# 가면 「그런 검사가 없다」가 아니라 **범위 오류(500)** 가 난다. 경계가 먼저 막는다.
_INT4_MAX = 2_147_483_647


class PurchaseReturnIn(BaseModel):
    """구매반품 한 건 — **검사를 가리킨다.** 로트 · 공급사 · 품목은 거기서 따라간다."""

    model_config = _ONLY_THE_FIELDS_WE_NAME

    # 검사 응답의 `inspection_id` 다.
    inspection_id: int = Field(gt=0, le=_INT4_MAX)
    settle_type: Present = Field(min_length=1, max_length=10)
    # **`> 0` 이다.** 돌려보낸 것이 없는 반품은 사건이 아니다(`ck_purchase_return_quantity`).
    quantity: float = Field(gt=0, allow_inf_nan=False)
    returned_by: Present = Field(min_length=1, max_length=50)
    # 재고 로트를 돌려보낼 때만 적는다 — 불합격분은 그 검사가 사유를 든다.
    nonconformity_code: Present | None = Field(default=None, max_length=30)


class PurchaseReturnOut(BaseModel):
    """반품이 선 뒤 남은 것.

    **돌려주는 칸마다 까닭이 있다**(감사 ⑫ NC-137) —

    - `purchase_return_id` — 반품 문서에는 다른 손잡이가 없다. 같은 검사에 반품이 여럿
      설 수 있어 `inspection_id` 로는 그 건을 가리키지 못한다
    - `ledger_entry_id` — 재고 로트를 돌려보냈으면 원장에서 빠졌다는 것을 부르는 쪽이
      확인할 자리다. **불합격분이면 비어 있다** — 재고가 된 적이 없어 뺄 줄이 없다.
      비어 있음이 그 구별을 말하므로 판정을 따로 싣지 않는다
    """

    purchase_return_id: int
    ledger_entry_id: int | None


# ── 거절의 본문 — **스펙이 그 이름을 든다** ────────────────────────────────


class RefusalDetail(BaseModel):
    """업무 규칙이 거절할 때 `detail[]` 에 실리는 줄.

    `type` 이 **기계가 읽는 자리**다. 이름 목록은 `Refusal` 한 벌이고 여기 다시
    적지 않는다 — 두 벌이면 갈린다.
    """

    loc: list[str]
    msg: str
    type: Refusal


class ValidationDetail(BaseModel):
    """pydantic 이 거절할 때 `detail[]` 에 실리는 줄.

    **같은 칸에 두 벌의 이름 공간이 산다.** `missing` · `extra_forbidden` 은
    pydantic 이 정한 이름이고 위의 `Refusal` 은 우리가 정한 이름인데, 둘 다
    `type` 으로 나간다. 그래서 `type` 을 하나의 닫힌 열거로 적으면 **거짓**이
    된다 — 두 모양을 함께 적어 부르는 쪽이 어느 쪽인지 가릴 수 있게 한다.
    """

    loc: list[str | int]
    msg: str
    type: str


class Refused(BaseModel):
    """검사 422 의 본문.

    **두 경로가 한 모양이다**(NC-75). 다른 것은 `type` 의 이름 공간뿐이고,
    그것을 위의 두 모델이 스펙에 적는다(감사 ⑫ NC-134).
    """

    detail: list[RefusalDetail | ValidationDetail]


class ReturnRefusalDetail(BaseModel):
    """반품의 업무 규칙이 거절할 때 `detail[]` 에 실리는 줄 — 이름은 `ReturnRefusal` 이 든다."""

    loc: list[str]
    msg: str
    type: ReturnRefusal


class ReturnRefused(BaseModel):
    """반품 422 의 본문 — `Refused` 와 **같은 모양이고 업무 이름의 열거만 다르다.**"""

    detail: list[ReturnRefusalDetail | ValidationDetail]


class Transport(StrEnum):
    """라우트 **밖에서** 나는 거절의 이름 — `detail[].type` 의 셋째 이름 공간.

    `Refusal` 은 업무 규칙이 거절할 때의 이름이고 이쪽은 **요청이 라우트에
    닿기 전이나 처리가 터진 뒤**의 이름이다. 둘을 한 열거로 합치지 않는 것은
    **층이 다르기 때문**이다 — 업무 이름은 관문 2 가 늘리고 이쪽은 늘지 않는다.

    **이 이름들이 여기 있는 이유는 NC-134 의 논거 그대로다.** 코드에만 있으면
    소비자가 문서화되지 않은 채 하드코딩하고, `http_error` 를 `path_error` 로
    고치는 커밋이 **어떤 검사도 물지 않고 어떤 스펙도 바꾸지 않은 채** 소비자의
    분기를 깬다 — NC-76 이 없앤 바로 그 모양이다(감사 ⑯ NC-160).
    """

    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class TransportDetail(BaseModel):
    """라우트 밖 거절의 `detail[]` 한 줄. `loc` 은 요청선 · 서버이고, 400 만 본문이다."""

    loc: list[str]
    msg: str
    type: Transport


class TransportRefused(BaseModel):
    """400 · 404 · 405 · 500 의 본문 — 422 와 **같은 모양이고 이름 공간만 다르다**."""

    detail: list[TransportDetail]
