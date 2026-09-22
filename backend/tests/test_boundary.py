"""인증이 서기 전의 경계 — 조각 11.

**지금 이 API 를 지키는 것은 코드가 아니다.** 권한 층은 사람이 늘어나는 날에
서고(앵커볼트 — 판정자는 칸이고 표가 아니다), 그때까지 `POST /inspections` 는
요청자에 대해 아무것도 묻지 않는다. 그러면 **경계는 무엇이고 누가 그것을
지키는가**가 남는다.

오늘의 답은 파일 두 개의 몇 줄이다 — compose 의 포트 바인딩과 빌드 컨텍스트
필터. 둘 다 **산문으로만 적혀 있으면 조용히 바뀐다**: 루프백을 떼는 한 글자도,
`.dockerignore` 를 지우는 것도 아무 검사도 물지 않았다. 「적어 두기만 하고
강제하지 않는 규칙을 만들지 않는다」가 이 파일의 이유다.

**이것은 권한 검사가 아니다.** 권한이 없는 동안의 경계일 뿐이고, 그 층이 서는
날 이 파일은 그 층을 가리키게 바뀐다.
"""

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# compose 의 목록 항목 중 **포트 매핑의 모양**만 고른다 — 숫자와 점과 콜론뿐인
# 따옴표 문자열이다. 명령이나 헬스체크는 이 모양을 갖지 않는다.
_PORT_MAPPING = re.compile(r'-\s+"([\d.:]+)"')


def test_every_published_port_is_bound_to_loopback() -> None:
    """**인증이 없는 쓰기 엔드포인트가 같은 네트워크에 열리지 않는다.**

    `8000:8000` 으로 한 글자가 바뀌면 같은 네트워크의 누구나 「검사원 1」을
    사칭해 특채 로트를 만들 수 있다. 데이터베이스도 같다 — 고정된 `erp`
    비밀번호가 붙어 있다.
    """
    published = _PORT_MAPPING.findall((REPO_ROOT / "compose.yaml").read_text())

    assert len(published) >= 2, published
    assert [port for port in published if not port.startswith("127.0.0.1:")] == []


def test_the_build_context_does_not_carry_the_secret_file() -> None:
    """**`.env` 가 이미지 레이어에 구워지지 않는다.**

    `Dockerfile` 이 빌드 컨텍스트를 통째로 `COPY` 하고 설정이 `.env` 를 읽는다.
    `.gitignore` 는 버전관리에서만 빼므로 이 자리를 대신하지 못한다 — 레이어는
    이미지를 받는 누구에게나 읽힌다.
    """
    ignored = {
        line.strip()
        for line in (BACKEND_ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {".env", ".env.*", ".venv/"} <= ignored, ignored


# 이미지가 살아 있으려면 컨텍스트에 **있어야** 하는 것들 — `docker-entrypoint.sh`
# 가 `alembic upgrade head` 와 시드를 돌리고 uvicorn 이 `app` 을 import 한다.
_MUST_REACH_THE_IMAGE = ("app", "migrations", "alembic.ini", "docker-entrypoint.sh")


def test_the_build_context_still_carries_what_the_image_needs_to_boot() -> None:
    """**빌드는 초록인데 기동만 깨지는 한 줄을 무는다** (감사 ⑮ NC-155).

    앞의 검사는 `.dockerignore` 에 세 줄이 **있는지**만 본다 — 한쪽 방향이다.
    `migrations/` 를 한 줄 더하면 `COPY . .` 는 하위 경로가 없어도 실패하지
    않으므로 **빌드도 초록이고 테스트도 전부 초록인데** 컨테이너는
    `alembic upgrade head` 에서 깨진다. 어긋내 확인했다.

    **이 검사가 못 보는 부류**(W-6 ③): 이름이 아니라 **패턴**으로 가리는 것
    (`*.ini` · `**/app`)과, 컨텍스트에는 있는데 `Dockerfile` 이 `COPY` 하지 않는
    것. 그리고 기동 자체는 여전히 아무도 띄우지 않는다 — 그 층은 `audit-ops` 다.
    """
    ignored = {
        line.strip().strip("/")
        for line in (BACKEND_ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }

    hidden = [name for name in _MUST_REACH_THE_IMAGE if name in ignored]
    assert hidden == [], f".dockerignore 가 이미지에 필요한 것을 가린다: {hidden}"


def test_the_entrypoint_is_executable() -> None:
    """**`ENTRYPOINT ["./docker-entrypoint.sh"]` 는 실행 비트를 요구한다** (NC-155).

    `shellcheck` 는 비트를 보지 않고 `docker build` 는 `ENTRYPOINT` 를 검증하지
    않는다 — 비트를 떼고 둘 다 돌려 보았고 **전부 초록이었다.** 무는 것이 여기
    말고는 없다.

    **이 검사가 못 보는 부류**(W-6 ③): 보는 것은 **체크아웃된 파일의 모드**이지
    git 이 들고 있는 값이 아니다. 둘은 보통 같지만(체크아웃이 git 의 비트를
    그대로 놓는다) 실행 비트를 갖지 못하는 파일시스템에서는 갈린다 — 거기서는
    이 검사가 거짓으로 빨개지지 참을 놓치지는 않는다.
    """
    entrypoint = BACKEND_ROOT / "docker-entrypoint.sh"

    assert (
        entrypoint.stat().st_mode & 0o111
    ), f"{entrypoint} 에 실행 비트가 없다 — `ENTRYPOINT` 가 그것을 요구한다"


def _test_database_url() -> str:
    """검사용 DB 주소. `conftest.py` 가 세우는 환경변수를 그대로 읽는다."""
    import os

    return os.environ["ERP_TEST_DATABASE_URL"]


def test_a_database_error_does_not_render_the_values_it_was_given() -> None:
    """**엔진 층에서도 사람이 보낸 값이 문자열에 실리지 않는다** (감사 ⑰ NC-164).

    SQLAlchemy 는 `StatementError` 에 `[parameters: {…}]` 를 붙인다. 500 처리기는
    DB 오류의 메시지를 아예 옮기지 않으므로 **오늘 그 문자열이 로그로 나가는
    길은 없지만**, 그것은 처리기 한 자리가 막고 있는 것이고 이 칸은 **엔진이
    만드는 모든 문자열**에 걸린다 — 다른 자리가 그 예외를 찍는 날 다시 열린다.

    어긋내 확인했다: `hide_parameters` 만 떼면 처리기가 막아 주어 API 쪽 검사는
    **초록으로 남는다.** 두 겹을 각각 무는 자리가 필요하다.
    """
    from sqlalchemy import text

    from app.db.base import create_db_engine

    # **엔진을 반드시 버린다.** 풀에 남은 연결은 나중에 수거되면서
    # `ResourceWarning` 을 내고, pytest 는 그것을 **그때 돌던 다른 검사**의
    # 실패로 올린다 — 실제로 그렇게 한 번 빨개졌다.
    engine = create_db_engine(_test_database_url())
    try:
        with engine.connect() as connection:
            try:
                connection.execute(
                    text("INSERT INTO a_table_that_does_not_exist (who) VALUES (:who)"),
                    {"who": "검사원 아무개"},
                )
            except Exception as exc:  # 문자열만 본다
                rendered = str(exc)
            else:  # pragma: no cover — 없는 표라 반드시 터진다
                raise AssertionError("터지지 않았다")
    finally:
        engine.dispose()

    assert "검사원 아무개" not in rendered, rendered
    assert "[parameters:" not in rendered, rendered
