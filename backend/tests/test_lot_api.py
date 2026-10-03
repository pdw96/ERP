"""읽는 엔드포인트 — 3단계 읽는 조각 B1.

**로트의 지금을 센다** — 잔량은 원장 줄의 합, 지금 만료일은 가장 최근 합격 재검사의 갱신
만료일(없으면 라벨의 것), 재검사를 기다리는가는 재검사 쓰기 경로가 받는 경계와 같다. 여기서
재는 것은 —

- 반품 · 재검사가 지난 뒤의 잔량과 만료일이 저장된 값이 아니라 센 값인가
- 「기다린다」의 경계가 재검사 쓰기 경로와 같은 날을 가르는가(만료일 당일은 아직 쓴다)
- 목록을 커서로 넘기면 겹치지도 빠지지도 않는가, 커서와 상한을 이름으로 거절하는가(ADR 0020)
"""

import base64
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import cursor as cursors
from app.api.app import app, session_scope
from app.core import clock, codes
from app.db.inspection import Inspection
from app.services.retests import retest
from app.services.returns import return_to_supplier
from tests.test_retest_path import (  # noqa: F401
    SHELF_LIFE,
    a_retest,
    an_expired_lot,
    planted,
)
from tests.test_return_path import _from_the_lot
from tests.test_write_path import GROUP


@pytest.fixture
def client(planted: Session) -> Iterator[TestClient]:  # noqa: F811
    app.dependency_overrides[session_scope] = lambda: planted
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _lot(client: TestClient, lot_id: int) -> dict[str, object]:
    response = client.get(f"/lots/{lot_id}")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def test_an_expired_lot_shows_what_it_holds_and_that_it_waits(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    lot = an_expired_lot(planted)

    assert _lot(client, lot.id) == {
        "lot_id": lot.id,
        "lot_number": lot.lot_number,
        "item_code": "RM-01",
        "received_quantity": 500.0,
        "balance": 500.0,
        "labelled_expiry_date": str(lot.expiry_date),
        "current_expiry_date": str(lot.expiry_date),
        "awaiting_retest": True,
    }


def test_a_return_takes_from_the_balance_not_from_the_received_quantity(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**잔량은 원장의 합이다** — 로트의 입고 수량은 그대로다."""
    lot = an_expired_lot(planted, quantity=100.0)
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 33.3))  # type: ignore[arg-type]
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 66.6))  # type: ignore[arg-type]

    body = _lot(client, lot.id)
    assert (body["received_quantity"], body["balance"]) == (100.0, pytest.approx(0.1))


def test_a_lot_sent_back_whole_does_not_wait(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**잔량이 없으면 기다리지 않는다** — 만료됐어도 다시 볼 물건이 없다."""
    lot = an_expired_lot(planted, quantity=10.0)
    return_to_supplier(planted, _from_the_lot(lot.inspection_id, 10.0))  # type: ignore[arg-type]

    body = _lot(client, lot.id)
    assert (body["balance"], body["awaiting_retest"]) == (0.0, False)


def test_the_current_expiry_is_the_latest_passed_retests(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**가장 최근에 합격한 재검사의 것이다** — 앞선 재검사가 낸 만료일이 지나 다시 재검사를
    받았으면 지금 만료일은 뒤엣것이다. 앞엣것은 이 테스트가 지난 날로 직접 넣는다."""
    lot = an_expired_lot(planted, expires=clock.today() - timedelta(days=100))
    earlier = clock.now() - timedelta(days=50)
    planted.add(
        Inspection(
            inspection_stage=codes.RETEST_STAGE,
            item_id=lot.item_id,
            item_type=lot.item_type,
            material_group=GROUP,
            target_lot_id=lot.id,
            judged_at=earlier,
            judged_by="검사원 1",
            result=codes.JUDGMENT_PASSED,
            renewed_expiry_date=earlier.date() + timedelta(days=10),
        )
    )
    planted.flush()
    retest(planted, a_retest(lot.id))

    body = _lot(client, lot.id)
    assert body["current_expiry_date"] == str(clock.today() + timedelta(days=SHELF_LIFE))


def test_a_passed_retest_renews_the_current_expiry_but_not_the_label(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**지금 만료일은 재검사의 것이고 라벨의 것은 고쳐지지 않는다**(ADR 0017 · 원칙 ⑦)."""
    lot = an_expired_lot(planted)
    labelled = lot.expiry_date
    retest(planted, a_retest(lot.id))

    body = _lot(client, lot.id)
    assert body["labelled_expiry_date"] == str(labelled)
    assert body["current_expiry_date"] == str(clock.today() + timedelta(days=SHELF_LIFE))
    assert body["awaiting_retest"] is False


def test_a_failed_retest_empties_the_lot_and_ends_the_wait(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    lot = an_expired_lot(planted)
    retest(planted, a_retest(lot.id, moisture=0.9))

    body = _lot(client, lot.id)
    assert (body["balance"], body["awaiting_retest"]) == (0.0, False)


@pytest.mark.parametrize(
    ("days_past", "waits"),
    [(1, True), (0, False)],
    ids=["expired-yesterday", "expires-today"],
)
def test_the_wait_starts_where_the_retest_path_draws_the_line(
    client: TestClient,
    planted: Session,  # noqa: F811
    days_past: int,
    waits: bool,
) -> None:
    """**만료일 당일까지는 쓴다** — 재검사 쓰기 경로가 받는 날과 같은 날부터 기다린다."""
    lot = an_expired_lot(planted, expires=clock.today() - timedelta(days=days_past))

    assert _lot(client, lot.id)["awaiting_retest"] is waits


def test_a_lot_without_an_expiry_does_not_wait(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """만료일이 없는 로트(설정기간 없는 품목)는 만료되지 않는다 — 재검사 쓰기 경로도
    받지 않는다. 만료일은 고정이라(`lot_expiry_stays_as_labelled`) 이 테스트의
    트랜잭션 안에서만 그 트리거를 끄고 비운다 — 되돌리면 함께 돌아온다."""
    lot = an_expired_lot(planted)
    planted.execute(text("ALTER TABLE lots DISABLE TRIGGER lot_expiry_stays_as_labelled"))
    lot.expiry_date = None
    planted.flush()

    body = _lot(client, lot.id)
    assert (body["current_expiry_date"], body["awaiting_retest"]) == (None, False)


def test_a_lot_nobody_made_is_named(client: TestClient) -> None:
    response = client.get("/lots/999999")

    assert response.status_code == 404, response.text
    assert response.json()["detail"] == [
        {"loc": ["path", "lot_id"], "msg": "그런 로트가 없다: 999999", "type": "unknown_lot"}
    ]


@pytest.mark.parametrize("lot_id", ["0", "-1", "2147483648", "abc"])
def test_a_lot_id_that_cannot_be_a_lot_stops_at_the_boundary(
    client: TestClient, lot_id: str
) -> None:
    """**`integer` 칸을 넘는 수는 경계가 막는다** — 데이터베이스까지 가면 범위 오류(500)다."""
    assert client.get(f"/lots/{lot_id}").status_code == 422


def _waiting(client: TestClient, **params: object) -> dict[str, object]:
    response = client.get("/lots", params={"awaiting_retest": "true", **params})
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def test_the_waiting_list_holds_only_the_lots_that_wait(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    waiting = an_expired_lot(planted, number="RM-01-250101-01")
    an_expired_lot(planted, expires=clock.today(), number="RM-01-250101-02")

    body = _waiting(client)
    assert [row["lot_id"] for row in body["lots"]] == [waiting.id]  # type: ignore[attr-defined]
    assert body["next_cursor"] is None
    # **꼭 맞게 받은 쪽도 마지막 쪽이다** — 남은 줄이 상한과 같으면 다음 커서가 없다.
    assert _waiting(client, limit=1)["next_cursor"] is None

    everything = client.get("/lots").json()
    assert len(everything["lots"]) == 2


def test_paging_through_the_list_neither_repeats_nor_skips(
    client: TestClient,
    planted: Session,  # noqa: F811
) -> None:
    """**대리키 순서로 넘긴다**(ADR 0020) — 쪽마다 하나씩 받아도 다 받고, 한 번씩만 받는다."""
    made = [an_expired_lot(planted, number=f"RM-01-250101-0{n}").id for n in range(1, 5)]

    seen: list[int] = []
    cursor: str | None = None
    for _ in range(10):
        body = _waiting(client, limit=1, **({"cursor": cursor} if cursor else {}))
        seen += [row["lot_id"] for row in body["lots"]]  # type: ignore[attr-defined]
        cursor = body["next_cursor"]  # type: ignore[assignment]
        if cursor is None:
            break

    assert seen == sorted(made)


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_a_limit_out_of_range_is_refused_not_trimmed(client: TestClient, limit: int) -> None:
    """**조용히 줄이지 않는다** — 줄이면 부르는 쪽은 다 받았다고 믿는다(ADR 0020)."""
    assert client.get("/lots", params={"limit": limit}).status_code == 422


def _tampered(stray: str) -> str:
    """내준 커서의 속에 base64 밖의 글자를 넷 끼운 것 — 넷이라 길이가 네 배수로 남아 디코더가
    그 글자들을 조용히 버리고 원래 커서를 읽는다."""
    issued = cursors.issue(cursors.LotCursor(awaiting_retest=True, after=1))
    version, _, packed = issued.partition(".")
    return f"{version}.{packed[:4]}{stray * 4}{packed[4:]}"


def _spelled(body: str) -> str:
    """뜻은 같거나 비슷하지만 이 판이 낸 글자가 아닌 커서."""
    packed = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"v1.{packed}"


@pytest.mark.parametrize(
    ("cursor", "name"),
    [
        ("garbage", "cursor_is_not_readable"),
        ("v2.eyJhIjp0cnVlLCJpZCI6MX0", "cursor_is_not_readable"),
        ("v1.bm90LWpzb24", "cursor_is_not_readable"),
        ("v1.한", "cursor_is_not_readable"),
        (_tampered("$"), "cursor_is_not_readable"),
        (_tampered("."), "cursor_is_not_readable"),
        (_spelled('{"a": true, "id": 1}'), "cursor_is_not_readable"),
        (_spelled('{"a":true,"id":2147483648}'), "cursor_is_not_readable"),
        (
            cursors.issue(cursors.LotCursor(awaiting_retest=False, after=1)),
            "cursor_is_for_another_list",
        ),
    ],
    ids=[
        "no-version",
        "unknown-version",
        "not-json",
        "not-ascii",
        "a-stray-dollar",
        "a-stray-dot",
        "not-as-issued",
        "beyond-integer",
        "another-list",
    ],
)
def test_a_cursor_this_list_did_not_issue_is_named(
    client: TestClient, cursor: str, name: str
) -> None:
    response = client.get("/lots", params={"awaiting_retest": "true", "cursor": cursor})

    assert response.status_code == 422, response.text
    assert response.json()["detail"][0]["type"] == name


def test_a_cursor_reads_back_what_it_was_issued_for() -> None:
    issued = cursors.LotCursor(awaiting_retest=True, after=42)

    assert cursors.read(cursors.issue(issued)) == issued


def test_the_spec_declares_what_the_read_paths_answer(client: TestClient) -> None:
    """**읽는 경로의 선언도 실제와 같다** — 없는 로트는 404 의 업무 이름이고, 이름은
    열린 문자열이다."""
    spec = client.get("/openapi.json").json()
    one = spec["paths"]["/lots/{lot_id}"]["get"]["responses"]

    assert one["404"]["content"]["application/json"]["schema"]["$ref"].endswith("/LotRefused")
    named = spec["components"]["schemas"]["LotRefusalDetail"]["properties"]["type"]
    assert named["x-known-values"] == [
        "unknown_lot",
        "cursor_is_not_readable",
        "cursor_is_for_another_list",
    ]
    assert "enum" not in named
    assert "404" not in spec["paths"]["/lots"]["get"]["responses"]
    assert client.post("/lots/1").status_code == 405
