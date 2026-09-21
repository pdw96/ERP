"""산문을 무는 게이트 — **적어 두기만 하고 강제하지 않는 규칙을 만들지 않는다.**

`CLAUDE.md` 가 규칙 셋을 들고 있는데 셋 다 지키는 것이 사람뿐이었다 — 그 상태로
통과한 결함이 대장에서 **가장 큰 무리**다. 여기서 둘을 기계에 옮긴다.

1. **단계 표기는 사실이 바뀔 때 함께 고친다** — 닫힌 단계를 「…에」로 가리키는
   현재형 문장은 그 단계가 끝나는 순간 거짓이 된다
2. **화면을 만들지 않는다** — `PRD.md` 성공기준의 「프런트엔드 디렉터리가 없다」

**셋째(수)는 게이트를 세우지 않는다.** 「테스트 N개」류는 무는 것보다 **지우는
쪽**이 답이고(`CLAUDE.md` 「될 수 있으면 적지 말고 목록을 가리킨다」), 실제로 NC-59
가 그 답을 냈다 — 세지 않는 문장으로 바꾸는 것.

> **이 게이트가 못 보는 부류**(W-6 ③ — 가드는 자기가 못 보는 것을 적는다):
> 아래 `_RECORDS` 에 통째로 빠진 두 파일 안에서 새로 나는 자리, 조사 없이
> 「1단계」만 쓴 문장, 그리고 **닫히지 않은 단계**에 대한 거짓 주장. 마지막
> 것은 기계가 가를 수 없다 — 그 단계가 아직 진행 중이면 참일 수 있다.
"""

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# 산문이 사는 확장자. 잠기는 자리가 아니라 **사람이 읽는 자리**를 본다.
_PROSE = ("*.py", "*.md", "*.sql", "*.toml", "*.yml", "*.yaml")

# **닫힌 단계를 어디서 아는가** — `docs/PRD-N단계.md` 가 서면 그 단계는 닫힌
# 것이다(`docs/PRD-1단계.md` 이 스스로 그렇게 적는다). 목록을 손으로 적지
# 않으므로 2단계가 닫히는 날 이 게이트가 저절로 넓어진다.
_CLOSED_RECORD = re.compile(r"PRD-(\d+)단계\.md$")

# **기록이라 소급해 고치지 않는 자리.** 예외가 늘면 이 목록이 diff 에 보인다.
_RECORDS = {
    "docs/PRD-1단계.md": "닫힌 기록 — 그 문서가 스스로 그렇게 적는다",
    "docs/audit/README.md": "회차 기록은 소급해 고치지 않는다 — 대장이 그렇게 정했다",
}

# **줄 단위 예외.** 과거형이거나, 규칙이 자기 예를 드는 줄이다.
_ALLOWED = {
    ("CLAUDE.md", "단계 표기는 사실이 바뀔 때"): "규칙이 자기 표기를 예로 든다",
    ("tests/test_prose.py", "그 단계가 끝나는 순간 거짓이"): "게이트가 자기 예를 든다",
    ("docs/audit/mutations.md", "로 되돌렸다"): "어긋낸 문장을 그대로 인용한 기록",
    ("docs/schema.md", "두지 않기로 했다"): "과거형 — 결정의 기록",
    ("docs/schema.md", "두지 않기로 정한 것"): "과거형 — 결정의 기록",
}


def _tracked() -> list[Path]:
    found: list[Path] = []
    for pattern in _PROSE:
        found += [
            path
            for path in REPO_ROOT.rglob(pattern)
            if ".venv" not in path.parts and ".git" not in path.parts
        ]
    return found


def test_a_stage_that_closed_is_not_written_as_if_it_were_now() -> None:
    """**닫힌 단계를 현재형으로 가리키지 않는다.**

    「1단계에서는 표만 선다」는 그 단계가 끝나는 순간 거짓이 되는데 아무것도
    물지 않았다 — NC-60 이 네 자리를 주웠고 그 전수가 코드가 아니라 사람이라
    **다섯째가 남아 있었다**(NC-92). 여기서부터는 기계가 센다.
    """
    closed = {
        match.group(1)
        for path in REPO_ROOT.rglob("docs/PRD-*단계.md")
        if (match := _CLOSED_RECORD.search(str(path)))
    }
    assert closed, "닫힌 단계의 기록이 하나도 없다 — 이 게이트가 아무것도 세지 않는다"
    looks_present = re.compile(rf"[{''.join(sorted(closed))}]단계에(는|서는|서)?[^가-힣]")

    said_now = []
    for path in _tracked():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in _RECORDS:
            continue
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if not looks_present.search(line):
                continue
            if any(key in relative and fragment in line for key, fragment in _ALLOWED):
                continue
            said_now.append(f"{relative}:{number} — {line.strip()}")

    assert said_now == [], "닫힌 단계를 현재형으로 가리킨다:\n" + "\n".join(said_now)


def test_there_is_still_no_screen() -> None:
    """**화면을 만들지 않는다** — `PRD.md` 의 성공기준이 이것을 요구한다.

    지금까지는 사람이 매번 눈으로 봤다. 프런트엔드는 디렉터리 하나로 조용히
    들어오고, 들어오는 순간 **스키마가 화면을 따라가기 시작한다.**
    """
    screens = [
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_dir() and path.name in {"frontend", "web", "ui", "client", "app"}
    ]

    assert screens == [], screens
    assert not (REPO_ROOT / "package.json").exists()
