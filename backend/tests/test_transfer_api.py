"""재고이동 쓰기 엔드포인트 — 4단계 조각 3(이동) PR C.

`tests/test_retest_api.py` 와 같은 자리를 본다 — 업무 규칙이 아니라 **경계**다. 받을 수 없는
것이 422 로 이름을 말하고 돌아가는가, 데이터베이스까지 가서 500 이 되는 입력이 경계에서
막히는가. 업무 규칙은 `tests/test_transfer_path.py` 가 본다.

라우트 밖 거절(400 · 404 · 405 · 500)과 그 선언은 쓰기 경로가 한 벌을 쓰므로
`tests/test_api.py` 가 경로마다 함께 잰다.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.app import app, session_scope
from app.api.schemas import ClosureType
from app.core import codes
from app.db.inventory import StockLedgerEntry, StockTransferClosure, StockTransferRequest
from app.services.transfers import TransferClosureRefusal, TransferRequestRefusal
from tests.test_transfer_path import (  # noqa: F401
    _committed_schema,
    a_live_lot,
    planted,
)

_REQUESTS, _CLOSURES = "/stock-transfer-requests", "/stock-transfer-closures"


@pytest.fixture
def client(planted: Session) -> Iterator[TestClient]:  # noqa: F811
    app.dependency_overrides[session_scope] = lambda: planted
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _asked(lot_id: int, quantity: float = 200.0, **overrides: object) -> dict[str, object]:
    return {"lot_id": lot_id, "quantity": quantity, "requested_by": "생산 1"} | overrides


def _closing(
    request_id: int, closure_type: str = codes.CLOSURE_PROCESSED, **overrides: object
) -> dict[str, object]:
    return {
        "transfer_request_id": request_id,
        "closure_type": closure_type,
        "closed_by": "자재 담당 1",
    } | overrides


def _request_id(client: TestClient, lot_id: int, quantity: float = 200.0) -> int:
    response = client.post(_REQUESTS, json=_asked(lot_id, quantity))
    assert response.status_code == 201, response.text
    request_id: int = response.json()["transfer_request_id"]
    return request_id


def test_a_request_comes_back_with_its_id(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**요청의 손잡이 하나를 돌려준다** — 처리 · 취소가 그것을 가리킨다."""
    lot = a_live_lot(planted)
    response = client.post(_REQUESTS, json=_asked(lot.id))

    assert response.status_code == 201, response.text
    assert response.json().keys() == {"transfer_request_id"}
    request = planted.get(StockTransferRequest, response.json()["transfer_request_id"])
    assert request is not None and (request.lot_id, request.quantity) == (lot.id, 200.0)


def test_processing_comes_back_with_both_ledger_lines(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**처리는 원장 두 줄의 id 를 돌려준다** — 출고 · 입고 순서다."""
    request_id = _request_id(client, a_live_lot(planted).id)

    response = client.post(_CLOSURES, json=_closing(request_id))

    assert response.status_code == 201, response.text
    assert response.json().keys() == {"ledger_entry_ids"}
    lines = [planted.get(StockLedgerEntry, i) for i in response.json()["ledger_entry_ids"]]
    assert [(line.txn_type, line.warehouse) for line in lines if line is not None] == [
        (codes.TXN_TRANSFER_OUT, codes.WAREHOUSE_RAW),
        (codes.TXN_TRANSFER_IN, codes.WAREHOUSE_PRODUCTION),
    ]


def test_cancelling_comes_back_with_no_ledger_line(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**취소는 빈 목록이다** — 비우지(`null`) 않는다. 부르는 쪽이 줄의 수로 분기하지 않는다."""
    request_id = _request_id(client, a_live_lot(planted).id)

    response = client.post(
        _CLOSURES, json=_closing(request_id, codes.CLOSURE_CANCELLED, closed_by="생산 2")
    )

    assert response.status_code == 201, response.text
    assert response.json() == {"ledger_entry_ids": []}


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        (_REQUESTS, _asked(2_000_000), TransferRequestRefusal.UNKNOWN_LOT),
        (_CLOSURES, _closing(2_000_000), TransferClosureRefusal.UNKNOWN_TRANSFER_REQUEST),
    ],
    ids=["request", "closure"],
)
def test_a_business_refusal_names_itself_in_the_same_shape(
    client: TestClient, path: str, payload: dict[str, object], expected: str
) -> None:
    """**업무 거절도 `detail[]` 한 모양이다** — `type` 이 그 경로의 열거의 이름이다."""
    response = client.post(path, json=payload)

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == [
        {"loc": ["body"], "msg": response.json()["detail"][0]["msg"], "type": expected}
    ]


def test_a_refused_processing_leaves_nothing_behind(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**거절된 처리는 종결도 원장 줄도 남기지 않는다** — 요청은 열린 채로 남아 취소할 수
    있다."""
    request_id = _request_id(client, a_live_lot(planted).id, quantity=800.0)

    response = client.post(_CLOSURES, json=_closing(request_id))

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == (
        TransferClosureRefusal.MORE_THAN_THE_RAW_WAREHOUSE_HOLDS
    )
    closures = select(func.count()).select_from(StockTransferClosure)
    assert planted.scalar(closures.where(StockTransferClosure.request_id == request_id)) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # `integer` 를 넘는 번호는 「없다」가 아니라 범위 오류(500)가 된다.
        ("lot_id", 2_147_483_648),
        ("lot_id", 0),
        ("quantity", 0),
        ("quantity", -1),
        ("quantity", "NaN"),
        ("requested_by", "　"),
        ("requested_by", "생산\x001"),
        ("requested_by", "가" * 51),
    ],
    ids=["lot-too-big", "lot-zero", "zero", "negative", "nan", "blank", "nul", "too-long"],
)
def test_what_the_database_would_break_on_is_refused_at_the_request_boundary(
    client: TestClient,
    planted: Session,  # noqa: F811
    field: str,
    value: object,
) -> None:
    """**데이터베이스까지 가면 500 이 되는 값**을 경계가 422 로 돌려보낸다."""
    response = client.post(_REQUESTS, json=_asked(a_live_lot(planted).id) | {field: value})

    assert response.status_code == 422, response.text
    assert field in response.json()["detail"][0]["loc"], response.json()


@pytest.mark.parametrize(
    ("field", "value", "type_"),
    [
        ("transfer_request_id", 2_147_483_648, "less_than_equal"),
        ("transfer_request_id", 0, "greater_than"),
        # **구분은 닫힌 열거다** — 다른 글자는 요청을 처리도 취소도 아닌 채로 끝낸다.
        ("closure_type", "보류", "enum"),
        ("closed_by", "\t", "value_error"),
        ("closed_by", "자재\x00담당", "value_error"),
    ],
    ids=["request-too-big", "request-zero", "unknown-type", "blank", "nul"],
)
def test_what_the_database_would_break_on_is_refused_at_the_closure_boundary(
    client: TestClient,
    planted: Session,  # noqa: F811
    field: str,
    value: object,
    type_: str,
) -> None:
    request_id = _request_id(client, a_live_lot(planted).id)
    response = client.post(_CLOSURES, json=_closing(request_id) | {field: value})

    assert response.status_code == 422, response.text
    assert (
        response.json()["detail"][0]["type"],
        field in response.json()["detail"][0]["loc"],
    ) == (
        type_,
        True,
    )


@pytest.mark.parametrize(
    ("path", "extra"),
    [
        # 시각은 서버가 적는다 — 보내도 조용히 버려지지 않는다.
        (_REQUESTS, {"requested_at": "2026-01-01T00:00:00"}),
        # 부분 처리는 없다 — 수량은 요청에서 끌어온다.
        (_CLOSURES, {"quantity": 1}),
    ],
    ids=["request-time", "closure-quantity"],
)
def test_an_unknown_field_is_refused(
    client: TestClient,
    planted: Session,  # noqa: F811
    path: str,
    extra: dict[str, object],
) -> None:
    """**모르는 칸은 받지 않는다**(ADR 0021)."""
    lot_id = a_live_lot(planted).id
    payload = _asked(lot_id) if path == _REQUESTS else _closing(_request_id(client, lot_id))

    response = client.post(path, json=payload | extra)

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("path", "refused", "detail", "names"),
    [
        (
            _REQUESTS,
            "TransferRequestRefused",
            "TransferRequestRefusalDetail",
            TransferRequestRefusal,
        ),
        (
            _CLOSURES,
            "TransferClosureRefused",
            "TransferClosureRefusalDetail",
            TransferClosureRefusal,
        ),
    ],
    ids=["request", "closure"],
)
def test_the_spec_lists_every_transfer_refusal_name(
    client: TestClient, path: str, refused: str, detail: str, names: type[object]
) -> None:
    """**이동의 거절 이름도 스펙이 든다** — 경로마다 자기 열거다(ADR 0014)."""
    spec = client.get("/openapi.json").json()

    answer = spec["paths"][path]["post"]["responses"]["422"]
    assert answer["content"]["application/json"]["schema"]["$ref"].endswith(f"/{refused}")
    named = spec["components"]["schemas"][detail]["properties"]["type"]
    assert named["x-known-values"] == [name.value for name in names]  # type: ignore[attr-defined]
    assert "enum" not in named


def test_the_closure_types_a_request_may_pick_are_the_ones_the_table_takes(
    client: TestClient,
) -> None:
    """**요청의 열거와 종결 표의 CHECK 는 같은 목록이다** — 열거로 적느라 두 벌이 됐다
    (`ClosureType`). 스펙에 실린 값까지 견준다."""
    assert tuple(kind.value for kind in ClosureType) == codes.CLOSURE_TYPES
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert schemas["ClosureType"]["enum"] == list(codes.CLOSURE_TYPES)


@pytest.mark.parametrize("closure_type", [codes.CLOSURE_PROCESSED, codes.CLOSURE_CANCELLED])
def test_a_201_means_the_commit_passed_the_deferred_check(
    engine: Engine, closure_type: str
) -> None:
    """**201 은 커밋이 지나간 뒤에 나간다** — 처리가 원장 두 줄을 가졌는지 묻는 지연 트리거까지.

    테스트 세션의 SAVEPOINT 안에서는 지연 트리거가 **한 번도 돌지 않는다.** 커밋이 실제로
    일어나는 스키마에 붙여, 엔드포인트가 응답 전에 하는 커밋이 그 트리거를 지나는 것을 본다.
    """
    with _committed_schema(engine, "transfer_api_commit") as (scoped, lot_id):

        def real_scope() -> Iterator[Session]:
            with Session(scoped) as session:
                yield session

        app.dependency_overrides[session_scope] = real_scope
        try:
            client = TestClient(app)
            request_id = _request_id(client, lot_id)
            response = client.post(_CLOSURES, json=_closing(request_id, closure_type))
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201, response.text
        with Session(scoped) as session:
            closure = session.scalars(
                select(StockTransferClosure).where(
                    StockTransferClosure.request_id == request_id
                )
            ).one()
            lines = session.scalars(
                select(StockLedgerEntry.id)
                .where(StockLedgerEntry.transfer_closure_id == closure.id)
                .order_by(StockLedgerEntry.id)
            ).all()
            assert (closure.closure_type, list(lines)) == (
                closure_type,
                response.json()["ledger_entry_ids"],
            )
