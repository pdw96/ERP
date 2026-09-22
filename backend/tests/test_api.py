"""쓰기 엔드포인트 — 조각 11.

**첫 공개 계약이다.** 여기서 검사하는 것은 업무 규칙이 아니라 **경계**다 —
밖에서 들어온 것을 어디까지 믿는가, 받을 수 없는 것을 어떻게 돌려보내는가,
그리고 **터졌을 때 무엇이 남는가.**

업무 규칙 자체는 `tests/test_write_path.py` 가 본다. 같은 것을 두 층에서 다시
확인하면 규칙이 바뀔 때 고칠 자리가 둘이 된다.
"""

import json
import logging
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.app import API_VERSION, app, session_scope
from app.core import codes
from app.db.constraints import blank_characters, is_present
from app.db.inventory import Lot, StockLedgerEntry
from app.services import incoming
from tests.test_write_path import _GRAIN, _MOISTURE, RECEIVED, prepared  # noqa: F401

_PAYLOAD = {
    "item_code": "RM-01",
    "supplier_code": "SUP-01",
    "supplier_lot_number": "SL-2026-0001",
    "quantity": 500.0,
    "judged_by": "검사원 1",
    "received_date": RECEIVED.isoformat(),
    "measurements": [
        {"item_code": _GRAIN, "value": 30.0},
        {"item_code": _MOISTURE, "value": 0.3},
    ],
}


@pytest.fixture
def client(prepared: Session) -> Iterator[TestClient]:  # noqa: F811
    """테스트 세션에 붙은 앱.

    **엔진을 갈아 끼우지 않고 의존성을 덮는다.** 앱이 자기 엔진을 만드는 것은
    운영의 모습이고, 테스트가 그 자리를 흉내 내면 흉내가 맞는지 아무도 모른다.
    """
    app.dependency_overrides[session_scope] = lambda: prepared
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_a_pass_comes_back_with_the_lot_number(client: TestClient) -> None:
    """**로트 번호를 돌려준다** — 부르는 쪽이 그것을 다시 물어보게 하지 않는다."""
    response = client.post("/inspections", json=_PAYLOAD)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result"] == codes.JUDGMENT_PASSED
    assert body["lot_number"] == "RM-01-260921-01"
    assert body["ledger_entry_id"] is not None


def test_a_failure_comes_back_without_a_lot(client: TestClient) -> None:
    """불합격도 **201 이다** — 검사는 정상적으로 받아졌고 판정이 불합격일 뿐이다.

    오류로 돌려보내면 부르는 쪽이 「적히지 않았다」로 읽는다. 적히지 않은 것과
    적혔는데 떨어진 것은 다른 사실이다.
    """
    payload = _PAYLOAD | {
        "measurements": [
            {"item_code": _GRAIN, "value": 99.0},
            {"item_code": _MOISTURE, "value": 0.3},
        ]
    }

    response = client.post("/inspections", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["result"] == codes.JUDGMENT_FAILED
    assert body["lot_id"] is None and body["lot_number"] is None


def test_something_we_cannot_judge_comes_back_named(client: TestClient) -> None:
    """**왜 막혔는지 모르는 실패는 고칠 수 없다.**

    제약이 터지면 나오는 말은 제약 이름이다. 그 앞에서 이름으로 말하고
    돌려보낸다 — 사람에게는 산문으로, **기계에게는 `type` 으로.**
    """
    response = client.post("/inspections", json=_PAYLOAD | {"item_code": "없는-품목"})

    assert response.status_code == 422
    refusal = response.json()["detail"][0]
    assert refusal["type"] == incoming.Refusal.UNKNOWN_ITEM
    assert "없는-품목" in refusal["msg"]


def test_both_kinds_of_422_have_the_same_shape(client: TestClient) -> None:
    """**같은 코드에 두 모양을 두지 않는다.**

    경계가 막은 것(모양이 틀렸다)과 업무가 막은 것(모양은 맞는데 받을 수 없다)이
    같은 422 로 나가는데 본문이 배열이기도 문자열이기도 하면, `for error in
    body["detail"]` 을 쓰는 클라이언트가 **422 를 처리하다 죽는다.** 그리고
    `/openapi.json` 은 그중 한 모양만 적으므로 다른 하나는 **스펙에 없는 응답**이다.
    """
    refused_by_the_boundary = client.post("/inspections", json=_PAYLOAD | {"quantity": -1.0})
    refused_by_the_work = client.post(
        "/inspections", json=_PAYLOAD | {"item_code": "없는-품목"}
    )

    for response in (refused_by_the_boundary, refused_by_the_work):
        assert response.status_code == 422, response.text
        body = response.json()
        assert isinstance(body["detail"], list), body
        for error in body["detail"]:
            assert {"loc", "msg", "type"} <= set(error), error
            assert isinstance(error["loc"], list), error


def test_a_delivery_that_has_not_arrived_is_refused(client: TestClient) -> None:
    """**아직 오지 않은 물건은 검사하지 못한다.**

    막지 않으면 합격일(오늘)이 입고일보다 앞서 `ck_lot_passed_after_arrival` 이
    물고, **잘 만들어진 요청 하나가 실마리 없는 500 으로 나간다.** 그리고 같은
    값이 불합격이면 201 로 지나간다 — 불합격은 로트를 만들지 않아 그 CHECK 에
    닿지 않기 때문이다. **경계가 그 갈림을 없앤다.**
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = client.post("/inspections", json=_PAYLOAD | {"received_date": tomorrow})

    assert response.status_code == 422, response.text
    refused = response.json()["detail"][0]
    assert refused["type"] == incoming.Refusal.RECEIVED_DATE_IS_IN_THE_FUTURE


def test_a_field_we_do_not_know_is_refused(client: TestClient) -> None:
    """**오타가 조용히 성공하지 않는다.**

    `specialAcceptance` 로 보내면 모르는 칸을 버리는 기본값에서는 **201 로
    성공하면서** 특채가 꺼진 채 읽힌다 — 받으려던 자재가 로트 없이 끝나고, 부르는
    쪽은 자기가 보낸 것이 반영됐다고 읽는다.
    """
    out_of_spec = _PAYLOAD | {
        "measurements": [
            {"item_code": _GRAIN, "value": 99.0},
            {"item_code": _MOISTURE, "value": 0.3},
        ],
        "specialAcceptance": True,
    }

    response = client.post("/inspections", json=out_of_spec)

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"] == ["body", "specialAcceptance"]


def test_a_break_answers_with_json_and_says_nothing_about_the_inside(
    prepared: Session,  # noqa: F811
) -> None:
    """**터져도 본문의 모양은 그대로다.**

    기본 처리기는 500 을 `text/plain` 으로 보낸다 — 오류를 `response.json()` 으로
    읽는 클라이언트는 그 자리에서 **파싱 오류**를 맞고, 무엇이 터졌는지가 아니라
    자기 파서가 깨진 것으로 본다. 그리고 제약 이름도 트레이스도 싣지 않는다.
    """

    def break_before_the_work() -> Iterator[Session]:
        raise RuntimeError("연결이 끊겼다 — 제약 이름 ck_something 과 함께")
        yield prepared  # pragma: no cover — 도달하지 않는다

    app.dependency_overrides[session_scope] = break_before_the_work
    try:
        broken = TestClient(app, raise_server_exceptions=False)
        response = broken.post("/inspections", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.json()
    assert body["detail"][0]["type"] == "internal_error"
    assert "ck_something" not in response.text


def test_the_spec_says_which_version_and_which_judgements(client: TestClient) -> None:
    """**기계가 읽는 계약이 자기 판과 값 집합을 말한다.**

    버전이 없으면 소비자가 붙은 뒤에 남는 길이 「조용히 깬다」와 「경로를 갈아 한
    번에 옮긴다」 둘뿐이다. `result` 가 자유 문자열이면 소비자는 「합격」을
    **문서화되지 않은 채** 하드코딩해야 한다.
    """
    spec = client.get("/openapi.json").json()

    assert spec["info"]["version"] == API_VERSION
    # **기본값은 「말하지 않은 것」이다.** 프레임워크의 기본 판과 같으면 적었는지
    # 여부가 밖에서 구별되지 않는다 — 이 줄이 없을 때 돌연변이가 통과했다.
    assert spec["info"]["version"] != FastAPI().version
    judged = spec["components"]["schemas"]["InspectionOut"]["properties"]["result"]
    assert judged["enum"] == list(codes.JUDGMENTS)


@pytest.mark.parametrize(
    ("field", "value"), [("quantity", -1.0), ("judged_by", ""), ("item_code", "")]
)
def test_the_boundary_refuses_what_it_cannot_believe(
    client: TestClient, field: str, value: object
) -> None:
    """**밖에서 들어온 것은 못 믿는다.**

    데이터베이스도 같은 것을 막지만, 그 자리까지 가기 전에 경계가 먼저
    돌려보낸다 — 제약 이름으로 나오는 말은 부르는 쪽에게 아무것도 알려 주지
    않는다.
    """
    response = client.post("/inspections", json=_PAYLOAD | {field: value})

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["judged_by", "supplier_lot_number"])
@pytest.mark.parametrize("blank", list(blank_characters()))
def test_the_boundary_refuses_what_only_looks_empty(
    client: TestClient,
    prepared: Session,  # noqa: F811
    field: str,
    blank: str,
) -> None:
    """**눈에는 비어 보이는데 비어 있지 않은 값** — 경계가 놓치면 500 이 나간다.

    `min_length=1` 은 길이만 본다. 공백 한 칸 · 탭 · 전각 공백(U+3000)은 그것을
    통과하고 `is_present()` CHECK 가 문다 — 그러면 검사원이 보는 것은 **제약
    이름이 담긴 500** 이고, 그것이 바로 이 엔드포인트가 없애려고 적어 둔 「왜
    막혔는지 모르는 실패」다.

    **두 층이 같은 목록을 말하는지 여기서 견준다.** 목록은 한 벌이지만
    (`app/db/constraints.py`) SQL 쪽 형태를 파이썬 글자로 푸는 자리가 있고, 그
    푸는 것이 틀리면 두 층이 조용히 갈린다 — 그래서 **데이터베이스에게 직접
    물어보고** 나서 경계를 두드린다.
    """
    seen_as_present = prepared.execute(
        text(f"SELECT {is_present(':value')}"), {"value": blank}
    ).scalar_one()
    assert seen_as_present is False, f"DB 는 {blank!r} 를 값이 있는 것으로 본다"

    response = client.post("/inspections", json=_PAYLOAD | {field: blank})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("literal", ["NaN", "Infinity"])
def test_the_boundary_refuses_a_number_you_cannot_count(
    client: TestClient, literal: str
) -> None:
    """**`NaN` 은 JSON 으로 실려 온다.**

    파이썬의 인코더는 내보내지 못해도 파서는 받는다. 들어오면 규격과의 비교가
    전부 거짓이 되어 합격도 불합격도 나오지 않고, 수량이면 이후의 모든 합계가
    `NaN` 이 된다 — 그래서 **본문을 손으로 지어** 그 문을 직접 두드린다.
    """
    body = json.dumps(_PAYLOAD).replace("500.0", literal)

    response = client.post(
        "/inspections", content=body, headers={"content-type": "application/json"}
    )

    assert response.status_code == 422


def test_nothing_lands_when_the_ledger_line_cannot_stand(prepared: Session) -> None:  # noqa: F811
    """**로트는 생겼는데 원장에 줄이 없는 상태가 없다** (성공기준 ③).

    원장 줄이 설 수 없게 만들어 두고 — 수불유형의 속성 줄을 없앤다 — 검사를
    받아 본다. 로트가 먼저 들어가므로 **한 트랜잭션이 아니면 로트만 남는다.**
    """
    from sqlalchemy import text as sql_text

    from app.services.incoming import receive
    from tests.test_write_path import _request

    prepared.execute(sql_text("DELETE FROM txn_type_attributes"))
    prepared.flush()

    with pytest.raises(IntegrityError):
        receive(prepared, _request())
    prepared.rollback()

    assert prepared.query(Lot).count() == 0
    assert prepared.query(StockLedgerEntry).count() == 0


def test_a_path_error_answers_in_the_same_shape(client: TestClient) -> None:
    """**거절의 본문은 라우트 밖에서도 한 모양이다** (감사 ⑫ NC-135).

    404 와 405 는 프레임워크가 `{"detail": "Not Found"}` 처럼 **문자열**로
    돌려준다. `for error in body["detail"]: error["type"]` 을 쓰는 클라이언트는
    글자를 돌다 죽으므로 **오류를 처리하는 코드가 오류에서 죽고**, 부르는 쪽은
    그것을 자기 파서가 깨진 것으로 본다.

    붙는 첫날에 가장 흔히 나는 응답이 바로 이 둘이다.
    """
    for response in (client.post("/inspection", json=_PAYLOAD), client.get("/inspections")):
        assert response.status_code in (404, 405), response.text
        detail = response.json()["detail"]
        assert isinstance(detail, list), detail
        assert detail[0].keys() == {"loc", "msg", "type"}, detail


def test_the_spec_lists_every_refusal_name(client: TestClient) -> None:
    """**거절의 이름을 `/openapi.json` 만 읽고 셀 수 있다** (감사 ⑫ NC-134).

    이름이 코드에만 있으면 소비자는 그것을 **문서화되지 않은 채 하드코딩**하고,
    이름이 늘어도 그것이 계약 변경으로 보이지 않는다 — `result` 가 `enum` 을
    싣는 이유와 같다.

    **두 벌을 견준다.** 스펙의 목록과 코드의 목록이 갈리는 순간 여기서 걸린다.
    """
    spec = client.get("/openapi.json").json()

    refused = spec["paths"]["/inspections"]["post"]["responses"]["422"]
    assert refused["content"]["application/json"]["schema"]["$ref"].endswith("/Refused")

    assert spec["components"]["schemas"]["Refusal"]["enum"] == [
        name.value for name in incoming.Refusal
    ]


def test_the_spec_declares_every_answer_that_actually_goes_out(client: TestClient) -> None:
    """**기계가 읽는 계약만 보는 소비자가 이 API 의 전부를 본다** (감사 ⑯ NC-160).

    처음에는 `201` 과 `422` 만 선언했는데, 그때도 404 · 405 · 500 이 같은
    `detail[]` 모양으로 나가고 있었다 — **스펙만 읽으면 둘만 내는 API** 였다.
    NC-134 가 스물셋에 대해 낸 논거가 그대로 남던 자리이고, `http_error` 를
    `path_error` 로 고치는 커밋이 **아무것도 물리지 않고** 소비자의 분기를 깼다.

    **실제로 찍어 견준다.** 선언 목록을 손으로 적으면 그 목록이 사본이 되어
    갈리므로, 라우트 밖 거절을 **실제로 일으켜** 그 상태 코드가 선언에 있는지를
    본다.

    **이 검사가 못 보는 부류**(W-6 ③): 이 검사가 일으키지 못하는 응답(500 은
    다른 검사가 일으킨다)과, 선언은 있는데 **모양이 다른** 경우 — 모양은 위의
    검사들이 본다.
    """
    spec = client.get("/openapi.json").json()
    declared = spec["paths"]["/inspections"]["post"]["responses"]

    # 라우트 밖 거절을 실제로 일으킨다 — 404 와 405.
    for response in (client.post("/inspection", json=_PAYLOAD), client.get("/inspections")):
        assert str(response.status_code) in declared, (response.status_code, sorted(declared))

    # 500 은 다른 검사가 일으키므로 선언만 본다. 세 상태가 같은 모양을 든다.
    for code in ("404", "405", "500"):
        schema = declared[code]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/TransportRefused"), (code, schema)


def test_the_spec_lists_every_transport_name(client: TestClient) -> None:
    """**라우트 밖 거절의 이름도 스펙이 든다** (감사 ⑯ NC-160).

    `Refusal` 과 같은 논거의 셋째 이름 공간이다 — `detail[].type` 은 NC-76 이
    **「고치면 깨지는 약속」**으로 선언한 칸이고, 그 칸에 약속 밖의 값이 실리면
    이름을 고치는 커밋이 파괴적 변경이 된다.

    **이 검사가 못 보는 부류**(W-6 ③): **이름의 변동 자체.** 양변이 같은 원천에서
    나오므로(스펙 쪽 값은 pydantic 이 이 열거에서 만든다) 이름을 더하거나 고치면
    **두 변이 함께 움직여 초록으로 남는다** — 어긋내 확인했다(`ghost` 를 더해도,
    `http_error` 를 `path_error` 로 고쳐도 통과한다). 이 검사가 무는 것은
    **배선이 끊길 때**다: `type` 이 `str` 로 돌아가거나, 열거가 인라인되어
    `$ref` 가 사라지거나, `responses=` 에서 모델이 빠지면 빨개진다.

    **그것으로 충분한 이유**는 NC-160 이 요구한 것이 「이름이 기계가 읽는 계약에
    있을 것」이기 때문이다 — 이제 이름을 고치면 `/openapi.json` 이 **함께 바뀌어
    diff 에 보인다.** 「이름이 바뀌면 검사가 문다」를 원하면 필요한 것은 **찍어 둔
    스펙과의 대조**이고, 그것은 이 저장소에 없다(감사 ⑯ OB-1).
    """
    spec = client.get("/openapi.json").json()

    assert spec["components"]["schemas"]["Transport"]["enum"] == [
        name.value for name in schemas.Transport
    ]


def test_the_spec_says_which_header_names_the_request(client: TestClient) -> None:
    """**`X-Request-Id` 의 규약이 밖이 읽는 자리에 있다** (감사 ⑯ NC-160).

    NC-145 가 그것을 「부르는 쪽이 『이 요청』이라고 말할 수 있게」 세웠는데,
    말할 자리가 스펙에 없으면 그 규약은 **우리끼리의 것**이다. 받은 값을
    존중하는 것까지가 그 규약이라 그것도 설명에 적힌다.
    """
    spec = client.get("/openapi.json").json()
    declared = spec["paths"]["/inspections"]["post"]["responses"]

    for code in ("201", "404", "405", "422", "500"):
        assert "X-Request-Id" in declared[code]["headers"], (code, declared[code])

    assert "Allow" in declared["405"]["headers"], declared["405"]


def test_a_status_that_may_not_carry_a_body_does_not_get_one(client: TestClient) -> None:
    """**덮개가 기본 처리기의 갈래를 떠안는다** (감사 ⑯ NC-161).

    `StarletteHTTPException` 의 기본 처리기는 둘을 한다 — 헤더를 넘기는 것과,
    **본문을 실으면 안 되는 상태 코드**를 본문 없이 돌려보내는 것. 덮으면서 앞의
    것을 잃은 자리가 NC-148 이고, 뒤의 것이 이것이다. `304` 에 본문과
    `Content-Length` 를 실으면 응답이 아니라 **프로토콜 오류**가 된다.

    앱에 그 상태로 던지는 라우트가 없으므로 **처리기를 직접 부른다** — 없는
    라우트를 세우면 그것이 계약면이 되어 버린다.
    """
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.api import app as api

    answer = api.answer_a_path_error_in_the_same_shape(
        Request({"type": "http", "method": "GET", "path": "/", "headers": []}),
        StarletteHTTPException(status_code=304, headers={"ETag": '"x"'}),
    )

    assert answer.body == b"", answer.body
    assert answer.headers["ETag"] == '"x"'
    assert "content-length" not in {name.lower() for name in answer.headers}


def test_every_answer_carries_an_id_that_names_the_request(client: TestClient) -> None:
    """**부르는 쪽이 「이 요청」이라고 말할 수 있다** (감사 ⑬ NC-145).

    실패한 트랜잭션은 통째로 롤백되어 **DB 에 한 줄도 남지 않는다.** 그래서 500
    의 유일한 흔적이 로그인데, 그 로그에 요청을 가리키는 축이 없으면 **동시에 두
    건만 들어와도** 어느 트레이스백이 그 요청인지 가를 수 없다.

    **본문이 아니라 헤더다** — 본문에 넣는 것이 계약 변경인지는 `audit-contract`
    가 판정할 자리다.
    """
    created = client.post("/inspections", json=_PAYLOAD)
    refused = client.post("/inspections", json={})

    assert created.headers.get("X-Request-Id"), created.headers
    assert refused.headers.get("X-Request-Id"), refused.headers
    assert created.headers["X-Request-Id"] != refused.headers["X-Request-Id"]


def test_an_id_the_caller_brought_is_not_replaced(client: TestClient) -> None:
    """**다음 층이 자기 축을 들고 오면 그것을 쓴다.**

    우리가 새로 지으면 축이 둘이 되고, 둘이면 이어 붙일 사람이 필요해진다.
    """
    response = client.post("/inspections", json={}, headers={"X-Request-Id": "from-above-01"})

    assert response.headers["X-Request-Id"] == "from-above-01"


def test_an_id_we_cannot_use_is_replaced_not_echoed(client: TestClient) -> None:
    """**밖에서 온 글자가 우리 로그 줄의 모양을 정하지 않는다.**

    이 값은 응답 헤더로 나가고 로그에 찍힌다. 모양을 좁히지 않으면 부르는 쪽이
    보낸 것이 그대로 그 두 자리에 앉는다 — **버리지는 않고 우리가 새로 짓는다.**
    """
    response = client.post("/inspections", json={}, headers={"X-Request-Id": "a b\tc" * 40})

    echoed = response.headers["X-Request-Id"]
    assert echoed != "a b\tc" * 40
    assert len(echoed) == 32 and echoed.isalnum(), echoed


def test_a_break_leaves_a_log_line_that_names_the_request(
    prepared: Session,  # noqa: F811
    caplog: pytest.LogCaptureFixture,
) -> None:
    """**실패는 DB 에 흔적을 남기지 않으므로 로그가 유일한 흔적이다** (감사 ⑬ NC-145).

    터진 트랜잭션은 통째로 롤백되어 한 줄도 남지 않는다. 그러니 그 요청을 다시
    찾아갈 길은 로그뿐인데, 거기에 **응답이 돌려준 것과 같은 축**이 없으면 부르는
    쪽이 들고 온 아이디로 아무것도 찾지 못한다.

    **안은 여전히 싣지 않는다** — 본문의 규칙이고, 로그는 그 규칙의 반대편이다.
    """

    def break_before_the_work() -> Iterator[Session]:
        raise RuntimeError("연결이 끊겼다")
        yield prepared  # pragma: no cover — 도달하지 않는다

    app.dependency_overrides[session_scope] = break_before_the_work
    try:
        broken = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.ERROR, logger="app.api"):
            response = broken.post(
                "/inspections", json=_PAYLOAD, headers={"X-Request-Id": "trace-me-01"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.headers["X-Request-Id"] == "trace-me-01"
    assert "trace-me-01" in caplog.text, caplog.text
    assert "POST" in caplog.text and "/inspections" in caplog.text


def test_a_method_error_still_says_which_method_works(client: TestClient) -> None:
    """**본문의 모양을 맞추느라 헤더를 잃지 않는다** (Codex 리뷰 P2).

    405 에는 프레임워크가 `Allow` 를 얹는다 — 부르는 쪽이 **어느 메서드가
    되는지**를 그 헤더에서 읽는다. 본문을 한 모양으로 다시 지으면서 응답을
    새로 만들면 그것이 조용히 사라진다.
    """
    response = client.get("/inspections")

    assert response.status_code == 405
    assert "POST" in response.headers.get("Allow", ""), dict(response.headers)


def test_a_break_leaves_the_cause_not_just_the_axis(
    prepared: Session,  # noqa: F811
    caplog: pytest.LogCaptureFixture,
) -> None:
    """**축만 있고 까닭이 없는 줄을 남기지 않는다** (Codex 리뷰 P2).

    500 처리기는 동기라 starlette 가 `run_in_threadpool` 로 부르고, 그 워커
    스레드에는 **활성 예외가 없다** — `logger.exception()` 은 `NoneType: None`
    만 찍는다. 요청 아이디는 있는데 **무엇이 터졌는지가 없는** 줄이 되고, 그것은
    이 로그가 세우려던 것의 반쪽이다.
    """

    def break_with_a_name() -> Iterator[Session]:
        raise RuntimeError("여기서 터졌다")
        yield prepared  # pragma: no cover — 도달하지 않는다

    app.dependency_overrides[session_scope] = break_with_a_name
    try:
        broken = TestClient(app, raise_server_exceptions=False)
        with caplog.at_level(logging.ERROR, logger="app.api"):
            broken.post("/inspections", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert "NoneType: None" not in caplog.text, caplog.text
    assert "RuntimeError" in caplog.text and "여기서 터졌다" in caplog.text, caplog.text
