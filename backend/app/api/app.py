"""첫 쓰기 엔드포인트 — 관문 1.

**엔드포인트는 하나다.** 수입검사 한 건을 받아 판정하고, 합격이면 로트와 원장
줄을 만든다. 「검사를 적는다 · 로트를 만든다 · 원장에 적는다」를 셋으로 나누면
**둘까지만 성공한 상태**가 생기고, 그것이 원칙 ⑦ 이 없애려는 것이다.

**읽는 엔드포인트가 없다.** 화면이 없으므로 부르는 쪽도 없고, 부르는 쪽이 없는
엔드포인트는 빈 기준정보와 같다.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.schemas import InspectionIn, InspectionOut
from app.db.base import create_db_engine, create_session_factory
from app.services.incoming import (
    IncomingInspection,
    Measurement,
    RefusedInspection,
    receive,
)

app = FastAPI(
    title="조기경보 ERP — 관문 1",
    summary="수입검사 한 건을 받아 판정하고, 합격이면 로트를 만든다.",
)

# **엔진은 앱마다 하나다.** 요청마다 만들면 연결 풀이 요청마다 새로 서고,
# 그것은 풀이 없는 것과 같다.
_engine = create_db_engine()
_session_factory = create_session_factory(_engine)


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
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": [
                {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


def session_scope() -> Iterator[Session]:
    """요청 하나가 트랜잭션 하나다.

    **터지면 아무것도 남지 않는다.** 검사 · 측정값 · 로트 · 원장 줄이 한 번에
    들어가거나 하나도 들어가지 않으며, 「로트는 생겼는데 원장에 줄이 없는」
    상태가 여기서 구조적으로 사라진다.
    """
    session = _session_factory()
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
) -> InspectionOut:
    """검사 한 건을 받는다.

    **받을 수 없는 것은 422 로 이름을 말하고 돌려보낸다.** 데이터베이스가 같은
    것을 한 번 더 막지만, 거기서 나오는 말은 제약 이름이라 검사원에게 아무것도
    알려 주지 않는다 — 「왜 막혔는지 모르는 실패」는 고칠 수 없는 실패다.
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(refused)
        ) from refused

    return InspectionOut(
        inspection_id=judged.inspection_id,
        result=judged.result,
        nonconformity_code=judged.nonconformity_code,
        lot_id=judged.lot_id,
        lot_number=judged.lot_number,
        ledger_entry_id=judged.ledger_entry_id,
    )
