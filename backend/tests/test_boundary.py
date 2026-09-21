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
