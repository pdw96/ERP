"""쓰기 엔드포인트 — 조각 11.

**첫 공개 계약이다.** 여기서 검사하는 것은 업무 규칙이 아니라 **경계**다 —
밖에서 들어온 것을 어디까지 믿는가, 받을 수 없는 것을 어떻게 돌려보내는가,
그리고 **터졌을 때 무엇이 남는가.**

업무 규칙 자체는 `tests/test_write_path.py` 가 본다. 같은 것을 두 층에서 다시
확인하면 규칙이 바뀔 때 고칠 자리가 둘이 된다.
"""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.app import app, session_scope
from app.core import codes
from app.db.constraints import blank_characters, is_present
from app.db.inventory import Lot, StockLedgerEntry
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
    돌려보낸다.
    """
    response = client.post("/inspections", json=_PAYLOAD | {"item_code": "없는-품목"})

    assert response.status_code == 422
    assert "없는-품목" in response.json()["detail"]


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
