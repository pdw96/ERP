"""요청과 응답의 모양 — **검증은 pydantic 한 벌로 한다.**

`app/services/incoming.py` 의 데이터클래스와 칸이 겹쳐 보이지만 둘은 다른 것을
맡는다. 여기 있는 것은 **밖에서 들어온 것을 못 믿는 층**이라 타입과 범위를 보고,
서비스 쪽은 이미 믿을 수 있는 값으로 업무를 한다. 경계를 하나로 합치면 HTTP 를
모르는 자리에서 HTTP 의 사정을 알게 된다.
"""

from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.db.constraints import blank_characters

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
    return value


Present = Annotated[str, AfterValidator(_present)]


class MeasurementIn(BaseModel):
    """검사원이 적은 실측값 하나."""

    item_code: Present = Field(min_length=1, max_length=30)
    # **`allow_inf_nan=False` 가 여기서도 선다.** JSON 은 `NaN` 을 실어 보낼 수
    # 있고, 들어오면 규격과의 비교가 전부 거짓이 되어 합격도 불합격도 나오지
    # 않는다. 데이터베이스도 같은 것을 막지만 거기서 나오는 말은 제약 이름이다.
    value: float = Field(allow_inf_nan=False)


class InspectionIn(BaseModel):
    """수입검사 한 건."""

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

    inspection_id: int
    result: str
    nonconformity_code: str | None
    lot_id: int | None
    lot_number: str | None
    ledger_entry_id: int | None
