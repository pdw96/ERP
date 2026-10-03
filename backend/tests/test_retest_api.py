"""재검사 쓰기 엔드포인트 — 3단계 조각 4.

`tests/test_return_api.py` 와 같은 자리를 본다 — 업무 규칙이 아니라 **경계**다. 받을 수 없는
것이 422 로 이름을 말하고 돌아가는가, 데이터베이스까지 가서 500 이 되는 입력이 경계에서
막히는가. 업무 규칙은 `tests/test_retest_path.py` 가 본다.

라우트 밖 거절(400 · 404 · 405 · 500)과 그 선언은 쓰기 경로가 한 벌을 쓰므로
`tests/test_api.py` 가 경로마다 함께 잰다.
"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.app import app, session_scope
from app.core import clock
from app.db.inspection import Inspection
from app.db.inventory import StockLedgerEntry
from app.services.retests import RetestRefusal
from tests.test_retest_path import (  # noqa: F401
    FINE,
    SHELF_LIFE,
    _committed_schema,
    an_expired_lot,
    planted,
)
from tests.test_write_path import _MOISTURE


@pytest.fixture
def client(planted: Session) -> Iterator[TestClient]:  # noqa: F811
    app.dependency_overrides[session_scope] = lambda: planted
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _payload(lot_id: int, moisture: float = FINE, **overrides: object) -> dict[str, object]:
    return {
        "lot_id": lot_id,
        "judged_by": "검사원 1",
        "measurements": [{"item_code": _MOISTURE, "value": moisture}],
    } | overrides


def test_a_pass_comes_back_with_its_new_expiry(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**새 만료일을 돌려준다** — 라벨에 다시 찍힐 값이라 부르는 쪽이 다시 셈하지 않는다."""
    response = client.post("/retests", json=_payload(an_expired_lot(planted).id))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body.keys() == {
        "inspection_id",
        "result",
        "nonconformity_code",
        "renewed_expiry_date",
        "ledger_entry_id",
    }
    assert body["result"] == "합격"
    assert body["renewed_expiry_date"] == str(clock.today() + timedelta(days=SHELF_LIFE))
    assert body["ledger_entry_id"] is None


def test_a_failure_comes_back_with_its_disposal_line(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    response = client.post("/retests", json=_payload(an_expired_lot(planted).id, moisture=0.9))

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["result"], body["renewed_expiry_date"]) == ("불합격", None)
    entry = planted.get(StockLedgerEntry, body["ledger_entry_id"])
    assert entry is not None and entry.retest_id == body["inspection_id"]


def test_a_business_refusal_names_itself_in_the_same_shape(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**업무 거절도 `detail[]` 한 모양이다** — `type` 이 `RetestRefusal` 의 이름이다."""
    lot = an_expired_lot(planted, expires=clock.today())
    response = client.post("/retests", json=_payload(lot.id))

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == [
        {
            "loc": ["body"],
            "msg": response.json()["detail"][0]["msg"],
            "type": RetestRefusal.LOT_HAS_NOT_EXPIRED.value,
        }
    ]
    assert lot.lot_number in response.json()["detail"][0]["msg"]
    assert (
        planted.scalar(
            select(func.count())
            .select_from(Inspection)
            .where(Inspection.target_lot_id == lot.id)
        )
        == 0
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # `integer` 를 넘는 번호는 「없다」가 아니라 범위 오류(500)가 된다.
        ("lot_id", 2_147_483_648),
        ("lot_id", 0),
        ("judged_by", "　"),
        ("judged_by", "검사\x00원"),
        ("nonconformity_code", "\t"),
        ("measurements", [{"item_code": _MOISTURE, "value": "NaN"}]),
    ],
    ids=["lot-too-big", "lot-zero", "blank-judge", "nul-judge", "blank-reason", "nan"],
)
def test_what_the_database_would_break_on_is_refused_at_the_boundary(
    client: TestClient,
    planted: Session,  # noqa: F811
    field: str,
    value: object,
) -> None:
    """**데이터베이스까지 가면 500 이 되는 값**을 경계가 422 로 돌려보낸다."""
    response = client.post(
        "/retests", json=_payload(an_expired_lot(planted).id) | {field: value}
    )

    assert response.status_code == 422, response.text
    assert field in response.json()["detail"][0]["loc"], response.json()


def test_an_unknown_field_is_refused(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**모르는 칸은 받지 않는다** — 특채(`special_acceptance`)를 보내도 조용히 버려지지
    않는다."""
    response = client.post(
        "/retests", json=_payload(an_expired_lot(planted).id, special_acceptance=True)
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_the_spec_lists_every_retest_refusal_name(client: TestClient) -> None:
    """**재검사의 거절 이름도 스펙이 든다** — 경로마다 자기 열거다(ADR 0014)."""
    spec = client.get("/openapi.json").json()

    refused = spec["paths"]["/retests"]["post"]["responses"]["422"]
    assert refused["content"]["application/json"]["schema"]["$ref"].endswith("/RetestRefused")
    assert spec["components"]["schemas"]["RetestRefusal"]["enum"] == [
        name.value for name in RetestRefusal
    ]
    assert schemas.RetestRefusalDetail.model_fields["type"].annotation is RetestRefusal
    assert spec["components"]["schemas"]["RetestOut"]["properties"]["result"]["enum"] == [
        "합격",
        "불합격",
    ]


def test_a_201_means_the_commit_passed_the_deferred_check(engine: Engine) -> None:
    """**201 은 커밋이 지나간 뒤에 나간다** — 떨어진 재검사의 폐기 줄을 묻는 지연 트리거까지.

    테스트 세션의 SAVEPOINT 안에서는 지연 트리거가 **한 번도 돌지 않는다.** 커밋이 실제로
    일어나는 스키마에 붙여, 엔드포인트가 응답 전에 하는 커밋이 그 트리거를 지나는 것을 본다.
    """
    with _committed_schema(engine, "retest_api_commit") as (scoped, lot_id):

        def real_scope() -> Iterator[Session]:
            with Session(scoped) as session:
                yield session

        app.dependency_overrides[session_scope] = real_scope
        try:
            response = TestClient(app).post("/retests", json=_payload(lot_id, moisture=0.9))
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201, response.text
        with Session(scoped) as session:
            entry = session.get(StockLedgerEntry, response.json()["ledger_entry_id"])
            assert entry is not None
            assert entry.retest_id == response.json()["inspection_id"]
