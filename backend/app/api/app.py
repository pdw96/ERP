"""첫 쓰기 엔드포인트 — 관문 1.

**엔드포인트는 하나다.** 수입검사 한 건을 받아 판정하고, 합격이면 로트와 원장
줄을 만든다. 「검사를 적는다 · 로트를 만든다 · 원장에 적는다」를 셋으로 나누면
**둘까지만 성공한 상태**가 생기고, 그것이 원칙 ⑦ 이 없애려는 것이다.

**읽는 엔드포인트가 없다.** 화면이 없으므로 부르는 쪽도 없고, 부르는 쪽이 없는
엔드포인트는 빈 기준정보와 같다.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from app.api.schemas import InspectionIn, InspectionOut
from app.db.base import create_db_engine, create_session_factory
from app.services.incoming import (
    IncomingInspection,
    Measurement,
    RefusedInspection,
    receive,
)

# **이 API 의 판이다 — 패키지의 판과 다른 축이다.** 같은 코드가 계약을 깨지 않고
# 여러 번 배포될 수 있고, 반대로 코드를 한 줄도 안 고치고 계약만 넓힐 수도 있다.
# 없으면 `/openapi.json` 이 프레임워크 기본값을 적어 **이 API 가 자기 판을 말하지
# 못한다** — 소비자가 붙은 뒤에는 「조용히 깬다」와 「경로를 갈아 한 번에 옮긴다」
# 둘만 남고, **병행 지원이라는 셋째 길이 지금 열리고 나중에는 열리지 않는다.**
#
# **자리를 둘만 쓴다.** 배포 번호가 아니라 계약의 판이라, 계약이 깨지면 앞자리가
# 호환되게 넓어지면 뒷자리가 움직인다. 셋째 자리는 움직일 일이 없다.
#
# **그리고 프레임워크의 기본값과 달라야 한다.** 기본값이 하필 `0.1.0` 이라, 그
# 값을 쓰면 「적었다」와 「안 적었다」가 밖에서 구별되지 않는다 — 검사가 통과하면서
# 아무것도 지키지 않게 된다(실제로 돌연변이가 그것을 드러냈다).
API_VERSION = "0.1"

app = FastAPI(
    title="조기경보 ERP — 관문 1",
    summary="수입검사 한 건을 받아 판정하고, 합격이면 로트를 만든다.",
    version=API_VERSION,
)


@lru_cache(maxsize=1)
def _sessions() -> sessionmaker[Session]:
    """**엔진은 앱마다 하나다.** 요청마다 만들면 연결 풀이 요청마다 새로 서고,
    그것은 풀이 없는 것과 같다.

    **다만 import 시점에 만들지 않는다.** 모듈 최상단에서 만들면 이 모듈을
    import 하는 것만으로 엔진이 서고, 그때 설정의 기본값(개발용 `erp`)을 든다 —
    `tests/conftest.py` 의 「앱 DB 금지」 가드는 **테스트가 돌 때** 환경변수를
    덮으므로 **수집 시점에 이미 선 엔진을 구조적으로 보지 못한다.** 덮기를 잊은
    테스트 하나면 개발자의 로컬에서 운영 성격의 DB 에 실제로 쓰고, CI 에는 그
    이름의 DB 가 없어 **거기서만 터진다** — 그 가드가 없애려고 선 바로 그
    사고다. 게으르게 만들면 가드가 자동으로 덮는다.
    """
    return create_session_factory(create_db_engine())


def _refusal(status_code: int, errors: list[dict[str, object]]) -> JSONResponse:
    """**거절의 본문은 한 모양이다.**

    422 가 어떤 때는 배열이고 어떤 때는 문자열이면, `for error in body["detail"]`
    을 쓰는 클라이언트가 **422 를 처리하다 죽는다.** 그리고 `/openapi.json` 은
    본문을 받는 라우트의 422 를 `HTTPValidationError` 로만 문서화하므로, 문자열
    `detail` 은 **스펙에 없는 응답**이 된다.

    세 칸의 뜻은 pydantic 이 정한 것을 그대로 쓴다 — `type` 이 **기계가 읽는
    자리**이고 `msg` 가 사람이 읽는 자리다.
    """
    return JSONResponse(status_code=status_code, content={"detail": errors})


@app.exception_handler(Exception)
def do_not_answer_a_break_with_plain_text(request: Request, exc: Exception) -> JSONResponse:
    """**터져도 본문의 모양은 그대로다.**

    기본 처리기는 500 을 `text/plain` 으로 보낸다 — 오류를 `response.json()` 으로
    읽는 클라이언트는 그 자리에서 **파싱 오류**를 맞고, 무엇이 터졌는지가 아니라
    자기 파서가 깨진 것으로 본다.

    **안을 싣지 않는다.** 제약 이름도 트레이스도 밖에서는 쓸 수 없는 말이고,
    실어 보내면 스키마를 그대로 알려 주는 자리가 된다. 어디에 무엇을 남길지는
    로그의 일이며 그 설비는 아직 없다.
    """
    return _refusal(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        [{"loc": ["server"], "msg": "처리하지 못했다", "type": "internal_error"}],
    )


@app.exception_handler(RequestValidationError)
def refuse_without_echoing_the_body(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """**들어온 값을 그대로 비추지 않는다.**

    기본 처리기는 무엇이 틀렸는지 말하면서 그 값을 함께 싣는다. 그런데 `NaN` 은
    JSON 으로 **들어올 수는 있어도 나갈 수는 없다** — 파이썬의 인코더가 거부한다.
    그래서 수량에 `NaN` 을 보내면 경계는 제대로 막아 놓고 **그 사실을 적어
    돌려보내는 자리에서 다시 터져**, 검사원은 422 대신 500 을 본다. 「왜 막혔는지
    모르는 실패」가 정확히 이렇게 난다.

    값을 빼면 틀린 자리와 이유는 그대로 남고 되비추는 문제만 사라진다. 검증되지
    않은 입력을 응답에 싣지 않는 것은 그 자체로도 옳다.
    """
    return _refusal(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ],
    )


def session_scope() -> Iterator[Session]:
    """요청 하나가 트랜잭션 하나다.

    **터지면 아무것도 남지 않는다.** 검사 · 측정값 · 로트 · 원장 줄이 한 번에
    들어가거나 하나도 들어가지 않으며, 「로트는 생겼는데 원장에 줄이 없는」
    상태가 여기서 구조적으로 사라진다.
    """
    session = _sessions()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@app.post("/inspections", response_model=InspectionOut, status_code=status.HTTP_201_CREATED)
def post_inspection(
    payload: InspectionIn, session: Annotated[Session, Depends(session_scope)]
) -> InspectionOut | JSONResponse:
    """검사 한 건을 받는다.

    **받을 수 없는 것은 422 로 이름을 말하고 돌려보낸다.** 제약이 터지고 나서
    나오는 말은 제약 이름이라 검사원에게 아무것도 알려 주지 않는다 — 「왜 막혔는지
    모르는 실패」는 고칠 수 없는 실패다. **어떤 갈래를 무엇이 막는지는 한 자리에만
    적는다** — `app/services/incoming.py` 의 `RefusedInspection` 이 든다.
    """
    try:
        judged = receive(
            session,
            IncomingInspection(
                item_code=payload.item_code,
                supplier_code=payload.supplier_code,
                supplier_lot_number=payload.supplier_lot_number,
                quantity=payload.quantity,
                judged_by=payload.judged_by,
                received_date=payload.received_date,
                measurements=tuple(
                    Measurement(item_code=row.item_code, value=row.value)
                    for row in payload.measurements
                ),
                nonconformity_code=payload.nonconformity_code,
                special_acceptance=payload.special_acceptance,
            ),
        )
    except RefusedInspection as refused:
        # **문자열 하나로 돌려보내지 않는다.** 같은 422 인데 본문의 모양이
        # 갈리면 부르는 쪽이 둘을 따로 처리해야 하고, 한쪽은 스펙에 없다.
        # `type` 에 실리는 이름은 **고치면 깨지는 약속**이다(`incoming.py`).
        return _refusal(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            [{"loc": ["body"], "msg": str(refused), "type": refused.code}],
        )

    return InspectionOut(
        inspection_id=judged.inspection_id,
        result=judged.result,
        nonconformity_code=judged.nonconformity_code,
        lot_id=judged.lot_id,
        lot_number=judged.lot_number,
        ledger_entry_id=judged.ledger_entry_id,
    )
