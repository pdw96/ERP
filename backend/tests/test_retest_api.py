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

from app.api.app import app, session_scope
from app.core import clock, codes
from app.db.inspection import Inspection
from app.db.inventory import Lot, StockLedgerEntry
from app.services.retests import RetestRefusal
from tests.test_retest_path import (  # noqa: F401
    FINE,
    SHELF_LIFE,
    _committed_schema,
    an_expired_lot,
    planted,
    split,
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
        "ledger_entry_ids",
    }
    assert body["result"] == "합격"
    assert body["renewed_expiry_date"] == str(clock.today() + timedelta(days=SHELF_LIFE))
    # **합격이면 빈 목록이다** — 비우지(`null`) 않는다. 부르는 쪽이 줄의 수로 분기하지
    # 않는다(ADR 0025)
    assert body["ledger_entry_ids"] == []


def test_a_failure_comes_back_with_its_disposal_line(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    response = client.post("/retests", json=_payload(an_expired_lot(planted).id, moisture=0.9))

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["result"], body["renewed_expiry_date"]) == ("불합격", None)
    (entry_id,) = body["ledger_entry_ids"]
    entry = planted.get(StockLedgerEntry, entry_id)
    assert entry is not None and entry.retest_id == body["inspection_id"]


def test_a_split_lot_comes_back_with_a_disposal_line_for_each_warehouse(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**나뉜 로트의 불합격은 폐기 줄 id 를 모두 돌려준다**(ADR 0025) — 옛 칸 하나로는 둘째 줄을
    돌려줄 수 없었다. 순서는 `codes.WAREHOUSES` 의 순서다."""
    lot = an_expired_lot(planted)
    split(planted, lot, 200.0)

    response = client.post("/retests", json=_payload(lot.id, moisture=0.9))

    assert response.status_code == 201, response.text
    body = response.json()
    entries = [planted.get(StockLedgerEntry, entry_id) for entry_id in body["ledger_entry_ids"]]
    assert [
        (entry.warehouse, entry.quantity, entry.retest_id) for entry in entries if entry
    ] == [
        (codes.WAREHOUSE_RAW, 300.0, body["inspection_id"]),
        (codes.WAREHOUSE_PRODUCTION, 200.0, body["inspection_id"]),
    ]


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
    named = spec["components"]["schemas"]["RetestRefusalDetail"]["properties"]["type"]
    assert named["x-known-values"] == [name.value for name in RetestRefusal]
    assert "enum" not in named
    judged = spec["components"]["schemas"]["RetestOut"]["properties"]["result"]
    assert judged["x-known-values"] == ["합격", "불합격"]
    assert "enum" not in judged


@pytest.mark.parametrize(
    ("moved", "warehouses"),
    [
        (None, [codes.WAREHOUSE_RAW]),
        # **나뉜 로트** — 「모든 창고가 비었는가」도 커밋 때의 지연 트리거가 묻는다(4단계 이동).
        (200.0, [codes.WAREHOUSE_RAW, codes.WAREHOUSE_PRODUCTION]),
    ],
)
def test_a_201_means_the_commit_passed_the_deferred_check(
    engine: Engine, moved: float | None, warehouses: list[str]
) -> None:
    """**201 은 커밋이 지나간 뒤에 나간다** — 떨어진 재검사의 폐기 줄을 묻는 지연 트리거까지.

    테스트 세션의 SAVEPOINT 안에서는 지연 트리거가 **한 번도 돌지 않는다.** 커밋이 실제로
    일어나는 스키마에 붙여, 엔드포인트가 응답 전에 하는 커밋이 그 트리거를 지나는 것을 본다.
    """
    with _committed_schema(engine, "retest_api_commit") as (scoped, lot_id):
        if moved is not None:
            with Session(scoped) as session:
                lot = session.get(Lot, lot_id)
                assert lot is not None
                split(session, lot, moved)
                session.commit()

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
            entries = [
                session.get(StockLedgerEntry, entry_id)
                for entry_id in response.json()["ledger_entry_ids"]
            ]
            assert [
                (entry.warehouse, entry.retest_id) for entry in entries if entry is not None
            ] == [(warehouse, response.json()["inspection_id"]) for warehouse in warehouses]
