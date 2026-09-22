"""첫 쓰기 엔드포인트 — 관문 1.

**엔드포인트는 하나다.** 수입검사 한 건을 받아 판정하고, 합격이면 로트와 원장
줄을 만든다. 「검사를 적는다 · 로트를 만든다 · 원장에 적는다」를 셋으로 나누면
**둘까지만 성공한 상태**가 생기고, 그것이 원칙 ⑦ 이 없애려는 것이다.

**읽는 엔드포인트가 없다.** 화면이 없으므로 부르는 쪽도 없고, 부르는 쪽이 없는
엔드포인트는 빈 기준정보와 같다.
"""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator, Mapping
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.schemas import (
    InspectionIn,
    InspectionOut,
    Refused,
    Transport,
    TransportRefused,
)
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
# **자리를 둘만 쓴다.** 배포 번호가 아니라 계약의 판이라 셋째 자리는 움직일 일이
# 없다.
#
# **그리고 지금은 움직이지 않는다.** 처음에는 「계약이 깨지면 앞자리가, 호환되게
# 넓어지면 뒷자리가 움직인다」고 적었는데 **그 규칙이 지켜지지 않았다** — 판이 선
# 뒤에 받던 요청을 거절하게 된 변경이 셋 들어가는 동안(NC-102 · 103 · 115) `0.1`
# 그대로였다. 적어 두기만 하고 강제하지 않는 규칙은 이 저장소가 금지한 것이라,
# 규칙을 지금 사실로 고쳤다 — **판은 `0.1` 로 고정하고, 계약을 좁히는 것은 그
# 창이 열려 있는 동안 자유롭다**(감사 ⑫ NC-136).
#
# **그 창이 닫히는 날을 이 저장소가 아는 사건으로 적는다** (감사 ⑯ NC-158).
# 처음에는 「첫 소비자가 붙는 날부터」라고 적었는데 그것은 **아무것도 가리키지
# 않는 기한**이었다 — 그날 이 저장소에서 바뀌는 것이 하나도 없어 지나가도 아무도
# 모른다. 대장이 같은 것을 이미 판정했다(「기한은 담당의 회차를 가리켜야 한다 —
# 가리키지 않는 기한은 지나가도 아무것도 드러나지 않는다」, W-1 이 세 회차를
# 놓친 이유). 창이 닫히는 것은 **읽는 엔드포인트가 서는 조각**이다 — 그날은
# 반드시 이 파일이 바뀌므로 조건이 스스로 드러나고, NC-80 이 `expiry_date` 를
# 미룰 때 쓴 기한과 같은 형태다.
#
# 그날 서는 규칙은 위에 적었던 그것이다 — 깨지면 앞자리, 넓어지면 뒷자리.
#
# **그리고 프레임워크의 기본값과 달라야 한다.** 기본값이 하필 `0.1.0` 이라, 그
# 값을 쓰면 「적었다」와 「안 적었다」가 밖에서 구별되지 않는다 — 검사가 통과하면서
# 아무것도 지키지 않게 된다(실제로 돌연변이가 그것을 드러냈다).
API_VERSION = "0.1"

app = FastAPI(
    title="조기경보 ERP — 관문 1",
    summary="수입검사 한 건을 받아 판정하고, 합격이면 로트를 만든다.",
    # **창이 열려 있다는 것을 밖이 읽는 자리에 적는다** (감사 ⑯ NC-158). 밖에서
    # 보이는 것이 `info.version` 하나뿐이면 **소비자는 이 계약이 좁혀도 되는 창
    # 안에 있다는 것을 알 길이 없다** — 알았다면 붙지 않았을 수도 있는 정보다.
    # `description` 은 `/openapi.json` 에 실린다.
    description=(
        "읽는 엔드포인트가 서기 전까지 이 계약은 **좁혀질 수 있고 판은"
        " 움직이지 않는다.** 그 조각이 서는 날부터 이동 규칙이 선다 —"
        " 깨지면 앞자리, 호환되게 넓어지면 뒷자리."
        "\n\n거절의 본문은 어느 경로에서나 `detail[]` 한 모양이다."
        " `detail[].type` 이 기계가 읽는 자리이고 이름 공간이 셋이다 —"
        " 업무 규칙의 `Refusal`, 라우트 밖의 `Transport`, 그리고 pydantic 이"
        " 정한 이름(`missing` · `extra_forbidden` 등). 앞의 둘은 이 스펙이"
        " 열거로 들고, **그 열거에 없는 값은 셋째 무리**다."
    ),
    version=API_VERSION,
)

# **요청 하나를 가리킬 것** (감사 ⑬ NC-145).
#
# 실패한 트랜잭션은 통째로 롤백되어 **DB 에 한 줄도 남지 않는다.** 그러므로 500
# 이 났을 때 유일한 흔적이 로그인데, 그 로그에 요청을 가리키는 축이 없었다 —
# uvicorn 의 접근 줄에는 시각도 식별자도 없고 트레이스백에도 없다. **동시에 두
# 건만 들어와도 어느 트레이스백이 그 요청인지 가를 수 없다.**
#
# **본문에는 싣지 않는다.** 500 본문에 참조 번호를 넣는 것이 계약 변경인지는
# `audit-contract` 가 판정할 자리이고, 그 판정 없이 넣으면 「안을 싣지 않는다」
# (NC-78)를 이쪽에서 뒤집는 것이 된다. 헤더는 그 판정 밖이다.
_REQUEST_ID_HEADER = "X-Request-Id"

# **스펙이 드는 헤더 규약.** 이름을 두 벌 두지 않으려고 위의 상수를 키로 쓴다.
_REQUEST_ID_SPEC = {
    _REQUEST_ID_HEADER: {
        "description": (
            "이 요청을 가리키는 값. 보내면 그대로 돌아오고, 없거나 모양이 맞지"
            " 않으면 우리가 짓는다."
        ),
        "schema": {"type": "string"},
    }
}
_ALLOW_SPEC = {
    "Allow": {
        "description": "이 경로가 받는 메서드.",
        "schema": {"type": "string"},
    }
}

# **받은 값을 그대로 되돌려 싣지 않는다.** 이 값은 응답 헤더로 나가고 로그에
# 찍히므로, 모양을 좁히지 않으면 **밖에서 온 글자가 우리 로그 줄의 모양을
# 정한다.** HTTP 헤더는 latin-1 이라 그 밖의 글자는 응답을 만들다 터지기도 한다.
# 좁히는 대신 **버리지 않는다** — 모양이 맞지 않으면 우리가 새로 짓는다.
_USABLE_REQUEST_ID = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")

_log = logging.getLogger("app.api")

# **시각이 없으면 축이 반쪽이다.** uvicorn 은 자기 로거만 설정하므로 이 로거는
# 루트로 올라가는데, 루트에 핸들러가 없으면 파이썬의 마지막 수단이 **형식 없이**
# 찍는다. 이미 누가 설정해 두었으면 건드리지 않는다.
if not logging.getLogger().handlers:  # pragma: no cover - 부팅 한 번
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s")


@app.middleware("http")
async def carry_an_id_that_names_this_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """**부르는 쪽이 「이 요청」이라고 말할 수 있게 한다.**

    부르는 쪽이 보낸 것이 있으면 그대로 쓴다 — 다음 층이 자기 축을 이미 들고
    있을 수 있고, 그때 우리가 새로 지으면 두 축이 갈린다.
    """
    brought = request.headers.get(_REQUEST_ID_HEADER, "")
    request_id = brought if _USABLE_REQUEST_ID.match(brought) else uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[_REQUEST_ID_HEADER] = request_id
    # **거절도 서버에 흔적을 남긴다** (감사 ⑰ NC-162). 축은 다섯 갈래 모두에
    # 나가고 스펙이 그것을 「이 요청을 가리키는 값」이라고 공표하는데, 그 값으로
    # 서버에서 찾을 수 있는 것이 500 하나뿐이었다 — 나머지 넷은 `grep` 0 건이고,
    # **uvicorn 접근 줄에는 축도 시각도 없어** 같은 초의 둘을 가르지 못한다.
    # 거절된 요청은 DB 에도 한 줄을 남기지 않으므로 **로그가 유일한 흔적**이라는
    # NC-145 의 전제가 거절에도 그대로 성립한다.
    #
    # **`WARNING` 으로 찍는다.** 루트 로거에 레벨을 세우지 않았으므로(`basicConfig`
    # 에 `level=` 이 없다) `INFO` 로 찍으면 한 줄도 나오지 않는다 — 레벨을 낮추면
    # 남의 라이브러리 줄까지 함께 열린다.
    #
    # **이 줄이 못 보는 부류**(W-6 ③): 성공한 요청(DB 에 줄이 남으므로 되짚을
    # 자리가 따로 있다)과, 미들웨어에 닿기 전에 끝나는 응답(끝 슬래시 307 ·
    # 전송 층이 내는 400). 그리고 부르는 쪽이 **같은 축을 계속 보내면** 여러
    # 요청이 한 줄에 겹친다 — 축의 유일성은 우리 것이 아니다.
    if response.status_code >= 400:
        _log.warning(
            "거절했다 request_id=%s %s %s -> %s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
        )
    return response


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


def _refusal(
    status_code: int,
    errors: list[dict[str, object]],
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """**거절의 본문은 한 모양이다.**

    422 가 어떤 때는 배열이고 어떤 때는 문자열이면, `for error in body["detail"]`
    을 쓰는 클라이언트가 **422 를 처리하다 죽는다.** 그리고 `/openapi.json` 은
    본문을 받는 라우트의 422 를 `HTTPValidationError` 로만 문서화하므로, 문자열
    `detail` 은 **스펙에 없는 응답**이 된다.

    세 칸의 뜻은 pydantic 이 정한 것을 그대로 쓴다 — `type` 이 **기계가 읽는
    자리**이고 `msg` 가 사람이 읽는 자리다.

    **본문의 모양을 맞추느라 헤더를 잃지 않는다.** 프레임워크가 거절에 얹는
    헤더가 있고(405 의 `Allow`), 응답을 다시 지으면 그것이 조용히 사라진다 —
    부르는 쪽은 **어느 메서드가 되는지**를 그 헤더에서 읽는다(Codex 리뷰 P2).
    """
    return JSONResponse(status_code=status_code, content={"detail": errors}, headers=headers)


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
    # **여기서 한 줄 찍는다.** 트레이스백은 starlette 가 다시 던져 uvicorn 이
    # 찍지만, 그 줄에는 이 요청을 가리키는 것이 없다. 안을 싣지 않는 것은 본문의
    # 규칙이고 **로그는 그 규칙의 반대편**이다 — 밖으로 나가지 않는다.
    request_id = getattr(request.state, "request_id", "-")
    # **`exception()` 을 쓰지 않는다.** 이 처리기는 동기라 starlette 가
    # `run_in_threadpool` 로 부르고, 그 워커 스레드에는 **활성 예외가 없다** —
    # `sys.exc_info()` 가 비어 `NoneType: None` 만 찍힌다(Codex 리뷰 P2, 실제로
    # 찍히는 것을 확인했다). 그러면 **축은 있는데 까닭이 없는** 줄이 남고, 이
    # 줄이 세우려던 것이 바로 그 둘을 한 자리에 두는 것이다. 예외를 손으로 넘긴다.
    #
    # **데이터베이스 오류는 까닭만 적고 그 말을 옮기지 않는다** (감사 ⑰ NC-164).
    # `hide_parameters=True` 가 SQLAlchemy 쪽 `[parameters: …]` 를 껐는데 **그것이
    # 한 겹이었다** — PostgreSQL 자신이 무결성 위반에 `DETAIL: Failing row
    # contains (…)` 를 붙여 **줄의 값 전부**를 되비춘다(검사가 그것을 잡았다).
    # 그 말을 옮기지 않고, 응답하는 사람이 실제로 쓰는 둘(SQLSTATE · 제약 이름)을
    # 골라 적는다 — 제약 이름은 **어느 규칙이 걸렸는가**라 SQLAlchemy 프레임
    # 스택보다 정확하다.
    #
    # **다른 예외는 그대로 스택을 싣는다.** 그쪽 메시지는 우리가 쓴 말이고,
    # NC-149 가 세운 것을 이 고침이 되돌리지 않는다.
    #
    # **이 줄이 못 보는 부류**(W-6 ③): 우리가 지은 예외 메시지에 사람이 보낸
    # 값을 직접 끼워 넣는 것. 그것은 이 자리가 아니라 **그 메시지를 짓는 자리**가
    # 막는다.
    if isinstance(exc, DBAPIError):
        diagnosis = getattr(exc.orig, "diag", None)
        _log.error(
            "요청을 처리하지 못했다 request_id=%s %s %s db_error=%s sqlstate=%s constraint=%s",
            request_id,
            request.method,
            request.url.path,
            type(exc.orig).__name__,
            getattr(exc.orig, "sqlstate", "-"),
            getattr(diagnosis, "constraint_name", None) or "-",
        )
    else:
        _log.error(
            "요청을 처리하지 못했다 request_id=%s %s %s",
            request_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )
    # **여기서 헤더를 다시 단다.** 500 은 위의 미들웨어를 지나오지 않는다 —
    # `ServerErrorMiddleware` 가 사용자 미들웨어 **바깥**에 서므로 그 미들웨어의
    # `call_next` 가 예외로 끊기고 응답에 헤더를 달 자리가 오지 않는다. 하필
    # **축이 가장 필요한 응답**이 그렇다.
    answer = _refusal(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        [{"loc": ["server"], "msg": "처리하지 못했다", "type": Transport.INTERNAL_ERROR}],
    )
    answer.headers[_REQUEST_ID_HEADER] = request_id
    return answer


@app.exception_handler(StarletteHTTPException)
def answer_a_path_error_in_the_same_shape(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """**본문을 받는 라우트 밖에서도 거절의 모양은 같다.**

    404 와 405 는 프레임워크가 `{"detail": "Not Found"}` 처럼 **문자열**로
    돌려준다. `for error in body["detail"]: error["type"]` 을 쓰는 클라이언트는
    글자를 돌다 `TypeError` 로 죽으므로, **오류를 처리하는 코드가 오류에서
    죽는다** — 그리고 부르는 쪽은 그것을 자기 파서가 깨진 것으로 본다.

    **처리기가 없어서가 아니다.** FastAPI 는 이 예외의 처리기를 기본으로 등록해
    두는데, 그 기본이 문자열을 싣는다. 그래서 **덮는다**(감사 ⑫ NC-135).

    경로·메서드 오류라 `loc` 은 본문이 아니라 요청선을 가리킨다.

    **덮으면 기본 처리기가 하던 것을 전부 떠안는다.** 그것은 둘이었다 — 헤더를
    넘기는 것과, **본문을 실으면 안 되는 상태 코드**를 본문 없이 돌려보내는 것.
    앞의 것은 Codex 리뷰가(NC-148), 뒤의 것은 감사 ⑯ 이 냈다(NC-160 의 형제
    NC-161). `304` · `204` 에 본문과 `Content-Length` 를 실으면 응답이 아니라
    **프로토콜 오류**가 되어 부르는 쪽이 받는 것은 끊긴 연결이다.

    **오늘 그 상태로 던지는 코드는 없다.** 그래도 되돌린 이유는 이것이 *새 가드를
    세우는* 것이 아니라 *프레임워크가 갖고 있던 갈래를 되찾는* 것이기 때문이다 —
    「닿지 않는 가드는 세우지 않는다」(NC-129)가 가르는 것은 **없던 것을 짓는**
    자리이고, 여기는 **덮으면서 잃은** 자리다. NC-148 과 같은 부류다.
    """
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=exc.headers)
    return _refusal(
        exc.status_code,
        [{"loc": ["path"], "msg": str(exc.detail), "type": Transport.HTTP_ERROR}],
        headers=exc.headers,
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

    **여기서 커밋하지 않는다.** `yield` 뒤의 코드는 **응답이 만들어져 나간 뒤에**
    돈다. 커밋을 여기 두면 커밋이 실패해도 201 은 이미 떠난 뒤라 되돌릴 수 없고,
    부르는 쪽은 **저장되지 않은 것을 저장됐다고 읽는다.** 커밋은 응답을 만들기
    전에, 엔드포인트가 한다 — 여기 남는 것은 **되돌리기와 닫기**다.
    """
    session = _sessions()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@app.post(
    "/inspections",
    response_model=InspectionOut,
    status_code=status.HTTP_201_CREATED,
    # **거절의 이름을 스펙이 든다.** 이것이 없으면 소비자가 `detail[].type` 의
    # 값을 문서화되지 않은 채 하드코딩하고, 이름이 늘어도 그것이 계약 변경으로
    # 보이지 않는다 — `result` 가 `enum` 을 싣는 이유와 같다(감사 ⑫ NC-134).
    #
    # **실제로 나가는 응답을 다 적는다** (감사 ⑯ NC-160). 처음에는 201 과 422 만
    # 적었는데, 그러면 **기계가 읽는 계약만 보는 소비자에게 이 API 는 둘만 내는
    # API** 다 — 404 · 405 · 500 이 같은 `detail[]` 모양으로 나가는데도 그렇다.
    # NC-134 가 스물셋에 대해 낸 논거가 그대로 남던 자리다.
    #
    # `X-Request-Id` 도 함께 적는다. NC-145 가 그것을 **「부르는 쪽이 『이 요청』
    # 이라고 말할 수 있게」** 세웠는데, 말할 자리가 스펙에 없으면 그 규약은
    # 우리끼리의 것이다. 받은 값을 존중하는 것까지가 그 규약이다.
    responses={
        # **성공도 그 헤더를 단다.** 미들웨어가 모든 응답에 달므로 201 만 빼면
        # 선언이 다시 실제보다 좁아진다 — NC-160 이 낸 그 모양이다(찍어서 봤다).
        status.HTTP_201_CREATED: {"headers": _REQUEST_ID_SPEC},
        status.HTTP_404_NOT_FOUND: {"model": TransportRefused, "headers": _REQUEST_ID_SPEC},
        status.HTTP_405_METHOD_NOT_ALLOWED: {
            "model": TransportRefused,
            "headers": _REQUEST_ID_SPEC | _ALLOW_SPEC,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": Refused,
            "headers": _REQUEST_ID_SPEC,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": TransportRefused,
            "headers": _REQUEST_ID_SPEC,
        },
    },
)
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

    # **응답을 만들기 전에 커밋한다.** 여기서 터지면 500 이 나가고, 그것이
    # 「저장되지 않았다」의 올바른 모양이다.
    session.commit()

    return InspectionOut(
        inspection_id=judged.inspection_id,
        result=judged.result,
        nonconformity_code=judged.nonconformity_code,
        lot_id=judged.lot_id,
        lot_number=judged.lot_number,
        ledger_entry_id=judged.ledger_entry_id,
    )
