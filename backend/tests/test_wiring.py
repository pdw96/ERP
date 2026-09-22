"""배선 — **한 트랜잭션이 실제로 커밋되는가.**

`tests/test_api.py` 는 의존성을 덮어 앱을 테스트 세션에 붙인다. 그 덮기가
편리한 만큼 **덮인 함수 자체는 한 줄도 실행되지 않는다** — `session_scope` 의
`commit` 과 `rollback` 이 그것이다. 지우면 엔드포인트는 **201 과 로트 번호를
돌려주고 아무것도 저장하지 않는데**, 읽는 엔드포인트도 화면도 없으므로 이
단계에서 그것을 알아챌 사람이 없다.

그래서 이 파일만 **진짜 `session_scope` 를 지나간다.** 앱이 자기 엔진으로 붙고,
심는 것도 보는 것도 **다른 연결**에서 한다 — 커밋되지 않은 것은 거기서 보이지
않기 때문이다.

> **여기서 확인하지 않는 것**: 업무 규칙(`test_write_path.py`)과 경계의 모양
> (`test_api.py`). 이 파일이 묻는 것은 **저장되는가와 남지 않는가** 둘뿐이다.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.app import _sessions, app, session_scope
from app.db.base import Base, create_session_factory
from tests.conftest import TEST_DATABASE_URL
from tests.test_api import _PAYLOAD
from tests.test_write_path import plant_master_data, prepared  # noqa: F401


@pytest.fixture
def committed(
    engine: Engine, tables: None, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Engine]:
    """**앱이 자기 엔진으로 붙는 판**을 세운다.

    기준정보를 **커밋해서** 심는다 — 롤백하는 세션 픽스처 안에 두면 앱의 연결이
    그것을 보지 못한다. 그래서 끝나고 표를 다시 세워 **뒤 테스트에 한 줄도
    남기지 않는다**: 커밋한 것은 롤백이 없앨 수 없다.
    """
    monkeypatch.setenv("ERP_DATABASE_URL", TEST_DATABASE_URL)
    _sessions.cache_clear()

    factory = create_session_factory(engine)
    with factory() as planting:
        plant_master_data(planting)
        planting.commit()
    try:
        yield engine
    finally:
        _close_the_app_engine()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


def _close_the_app_engine() -> None:
    """**앱이 쥔 연결을 닫고 캐시를 비운다.**

    `cache_clear()` 만 하면 엔진 객체의 참조만 사라지고 **풀에 든 연결은 열린
    채로 남는다.** 나중에 가비지 컬렉터가 그것을 거둘 때 psycopg 가
    `ResourceWarning` 을 내고, 이 저장소는 경고를 실패로 올리므로 **그 순간에
    돌던 다른 테스트가 빨개진다** — 실제로 그렇게 났고 범인이 매번 달랐다.
    """
    _sessions().kw["bind"].dispose()
    _sessions.cache_clear()


def _rows(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_a_pass_is_actually_committed(committed: Engine) -> None:
    """**201 을 돌려주고 아무것도 저장하지 않는 상태가 없다.**

    성공기준 ③ 을 지키는 검사(`test_api.py`)는 서비스 함수를 직접 부르므로 이
    배선을 지나가지 않는다 — 한 트랜잭션인 것은 증명되는데 **그 트랜잭션이
    커밋되는지는 그쪽이 묻지 않는다.** 여기서 묻는다.
    """
    response = TestClient(app).post("/inspections", json=_PAYLOAD)

    assert response.status_code == 201, response.text
    assert response.json()["lot_number"] == "RM-01-260921-01"
    # **다른 연결에서 본다.** 커밋되지 않았으면 여기서 0 이다.
    assert _rows(committed, "lots") == 1
    assert _rows(committed, "stock_ledger_entries") == 1
    assert _rows(committed, "inspections") == 1


def test_nothing_is_left_when_the_request_breaks(
    committed: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**터지면 아무것도 남지 않는다** — 롤백도 실행되는 자리다.

    원장 줄이 설 수 없게 해 두고 검사를 보낸다. 로트가 먼저 들어가므로 되돌리지
    않으면 **로트만 남는다.**
    """
    with committed.begin() as conn:
        conn.execute(text("DELETE FROM txn_type_attributes"))

    broken = TestClient(app, raise_server_exceptions=False)
    response = broken.post("/inspections", json=_PAYLOAD)

    assert response.status_code == 500, response.text
    assert _rows(committed, "lots") == 0
    assert _rows(committed, "inspections") == 0


class _SessionThatCannotCommit:
    """커밋만 실패하는 세션 — 나머지는 그대로 넘긴다."""

    def __init__(self, session: object) -> None:
        self._session = session

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)

    def commit(self) -> None:
        raise RuntimeError("커밋이 실패했다 — 연결이 끊겼다고 하자")


def test_a_commit_that_fails_does_not_answer_201(prepared: Session) -> None:  # noqa: F811
    """**커밋은 응답을 만들기 전에 해야 한다.**

    `yield` 를 쓰는 의존성의 뒷부분은 **응답이 만들어져 나간 뒤에** 돈다. 커밋을
    거기 두면 커밋이 실패해도 201 은 이미 떠난 뒤라 되돌릴 수 없고, 부르는 쪽은
    **저장되지 않은 것을 저장됐다고 읽는다** — 되돌릴 대상조차 남기지 않는
    실패다.

    그래서 여기서 커밋을 터뜨리고 **상태 코드를 본다.** 커밋이 의존성 뒤로
    돌아가면 이 검사가 201 을 받는다.
    """
    app.dependency_overrides[session_scope] = lambda: _SessionThatCannotCommit(prepared)
    try:
        broken = TestClient(app, raise_server_exceptions=False)
        response = broken.post("/inspections", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()
        prepared.rollback()

    assert response.status_code == 500, response.text
    assert response.json()["detail"][0]["type"] == "internal_error"


def test_the_app_does_not_reach_for_the_default_database() -> None:
    """**앱의 엔진이 가드보다 먼저 서지 않는다.**

    모듈 최상단에서 엔진을 만들면 이 모듈을 import 하는 것만으로 엔진이 서고,
    그때 설정의 기본값(개발용 `erp`)을 든다 — `conftest.py` 의 「앱 DB 금지」
    가드는 **테스트가 돌 때** 덮으므로 **수집 시점에 이미 선 엔진을 구조적으로
    보지 못한다.** 덮기를 잊은 테스트 하나면 개발자의 로컬에서는 운영 성격의 DB
    에 실제로 쓰고 CI 에서만 터진다.

    가드가 덮어 둔 값은 닿을 수 없는 주소이므로, 게으르게 만들면 여기서 **붙지
    못하는 것이 정상**이다. 최상단에서 만들면 붙어 버린다.
    """
    _sessions.cache_clear()
    try:
        bound = _sessions().kw["bind"].url
    finally:
        _close_the_app_engine()

    assert bound.database == "erp_must_not_be_used", bound
