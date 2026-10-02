"""반품 쓰기 엔드포인트 — 3단계 조각 2.

`tests/test_api.py` 와 같은 자리를 본다 — 업무 규칙이 아니라 **경계**다. 받을 수 없는
것이 422 로 이름을 말하고 돌아가는가, 데이터베이스까지 가서 500 이 되는 입력이 경계에서
막히는가. 업무 규칙은 `tests/test_return_path.py` 가 본다.

라우트 밖 거절(400 · 404 · 405 · 500)과 그 선언은 두 경로가 한 벌을 쓰므로
`tests/test_api.py` 가 두 경로에 함께 잰다.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.app import app, session_scope
from app.core import codes
from app.db.inventory import PurchaseReturn, StockLedgerEntry
from app.services.returns import ReturnRefusal
from tests.factories import add_code
from tests.test_return_path import (  # noqa: F401
    IN_KIND,
    _committed_schema,
    _failed,
    _passed,
    planted,
)
from tests.test_write_path import _FOREIGN_REASON

# 공통코드에는 설 수 있는데 반품 문서의 칸(`String(10)`)에는 들지 않는 정산 구분.
_TOO_LONG_TO_KEEP = "대물정산-분할반품-예외"


@pytest.fixture
def client(planted: Session) -> Iterator[TestClient]:  # noqa: F811
    app.dependency_overrides[session_scope] = lambda: planted
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _payload(inspection_id: int, **overrides: object) -> dict[str, object]:
    return {
        "inspection_id": inspection_id,
        "settle_type": IN_KIND,
        "quantity": 100.0,
        "returned_by": "자재 담당 1",
    } | overrides


def test_a_lot_return_comes_back_with_its_ledger_line(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    inspection_id = _passed(planted)

    response = client.post(
        "/purchase-returns", json=_payload(inspection_id, nonconformity_code=_FOREIGN_REASON)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body.keys() == {"purchase_return_id", "ledger_entry_id"}
    entry = planted.get(StockLedgerEntry, body["ledger_entry_id"])
    assert entry is not None and entry.purchase_return_id == body["purchase_return_id"]


def test_a_failed_return_comes_back_without_a_ledger_line(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**비어 있음이 「재고가 된 적 없다」를 말한다** — 판정을 따로 싣지 않는다."""
    response = client.post("/purchase-returns", json=_payload(_failed(planted)))

    assert response.status_code == 201, response.text
    assert response.json()["ledger_entry_id"] is None


def test_a_business_refusal_names_itself_in_the_same_shape(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**업무 거절도 `detail[]` 한 모양이다** — `type` 이 `ReturnRefusal` 의 이름이다."""
    response = client.post("/purchase-returns", json=_payload(_passed(planted)))

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == [
        {
            "loc": ["body"],
            "msg": response.json()["detail"][0]["msg"],
            "type": ReturnRefusal.REASON_IS_MISSING.value,
        }
    ]
    assert planted.scalar(select(func.count()).select_from(PurchaseReturn)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # 돌려보낸 것이 없는 반품은 사건이 아니다 — `ck_purchase_return_quantity` 가 문다.
        ("quantity", 0.0),
        ("quantity", -1.0),
        # `integer` 를 넘는 번호는 「없다」가 아니라 범위 오류(500)가 된다.
        ("inspection_id", 2_147_483_648),
        ("inspection_id", 0),
        # 공통코드 칸(30자)에는 들지만 반품 칸(10자)을 넘는 정산 구분 — 아래에서 심는다.
        # 경계가 없으면 「그런 정산 구분이 없다」를 지나 넣는 자리에서 터진다.
        ("settle_type", _TOO_LONG_TO_KEEP),
        ("returned_by", "　"),
        ("nonconformity_code", "\t"),
    ],
)
def test_what_the_database_would_break_on_is_refused_at_the_boundary(
    client: TestClient,
    planted: Session,  # noqa: F811
    field: str,
    value: object,
) -> None:
    """**데이터베이스까지 가면 500 이 되는 값**을 경계가 422 로 돌려보낸다.

    **정산 구분은 실제로 있는 코드로 잰다.** 처음에는 없는 긴 코드를 보냈는데, 경계를 빼도
    「그런 정산 구분이 없다」(422)로 막혀 이 검사가 **다른 까닭으로** 빨개졌다(어긋내 확인했다).
    """
    add_code(planted, codes.SETTLE_TYPE, _TOO_LONG_TO_KEEP, "칸보다 긴 정산 구분")
    planted.flush()
    response = client.post(
        "/purchase-returns", json=_payload(_failed(planted)) | {field: value}
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["loc"][-1] == field, response.json()


def test_an_unknown_field_is_refused(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**모르는 칸은 받지 않는다** — `lotId` 같은 오타가 조용히 버려지지 않는다."""
    response = client.post("/purchase-returns", json=_payload(_failed(planted), lot_id=1))

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_the_spec_lists_every_return_refusal_name(client: TestClient) -> None:
    """**반품의 거절 이름도 스펙이 든다** — 검사의 `Refusal` 과 같은 논거다(감사 ⑫ NC-134).

    **열거를 경로마다 둔다.** 검사의 422 가 반품의 이름까지 싣지 않는다는 것도 함께 본다 —
    한 열거로 합치면 검사를 부르는 쪽이 날 수 없는 이름까지 분기로 적는다.
    """
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]

    returned = paths["/purchase-returns"]["post"]["responses"]["422"]
    assert returned["content"]["application/json"]["schema"]["$ref"].endswith("/ReturnRefused")
    inspected = paths["/inspections"]["post"]["responses"]["422"]
    assert inspected["content"]["application/json"]["schema"]["$ref"].endswith("/Refused")

    assert spec["components"]["schemas"]["ReturnRefusal"]["enum"] == [
        name.value for name in ReturnRefusal
    ]
    assert schemas.ReturnRefusalDetail.model_fields["type"].annotation is ReturnRefusal


def test_a_201_means_the_commit_passed_the_deferred_check(engine: Engine) -> None:
    """**201 은 커밋이 지나간 뒤에 나간다** — 문서 → 원장 줄을 묻는 지연 트리거까지.

    위의 검사들은 테스트 세션의 SAVEPOINT 안이라 바깥 커밋이 없고, 그래서 지연 트리거가
    **한 번도 돌지 않는다.** 여기서는 커밋이 실제로 일어나는 스키마에 붙여, 엔드포인트가
    응답 전에 하는 커밋이 그 트리거를 지나는 것을 본다.
    """
    with _committed_schema(engine, "return_api_commit") as scoped:
        with Session(scoped) as session:
            inspection_id = _passed(session)
            session.commit()

        def real_scope() -> Iterator[Session]:
            with Session(scoped) as session:
                yield session

        app.dependency_overrides[session_scope] = real_scope
        try:
            response = TestClient(app).post(
                "/purchase-returns",
                json=_payload(inspection_id, nonconformity_code=_FOREIGN_REASON),
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201, response.text
        with Session(scoped) as session:
            document = session.get(PurchaseReturn, response.json()["purchase_return_id"])
            entry = session.get(StockLedgerEntry, response.json()["ledger_entry_id"])
            assert document is not None and entry is not None
            assert entry.purchase_return_id == document.id
