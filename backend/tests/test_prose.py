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


_MUTATIONS = REPO_ROOT / "docs/audit/mutations.md"

# 묶음 제목이 드는 커밋. 이 파일의 관용구가 백틱이라 백틱까지 본다 — 맨 글자만
# 세면 산문 속의 우연한 16진 토막이 통과시킨다.
_COMMIT = re.compile(r"`[0-9a-f]{7,40}`")


def _bundles_with_a_table(text: str) -> list[tuple[int, str]]:
    """`## ` 절 가운데 **표를 든 것**만 돌려준다 — 그것이 어긋냄의 기록이다.

    제목의 문구에 기대지 않는 이유는 위 게이트의 독스트링에 있다(NC-153).
    """
    found: list[tuple[int, str]] = []
    heading: tuple[int, str] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            heading = (number, line)
        elif line.startswith("|") and heading is not None:
            found.append(heading)
            heading = None
    return found


def test_a_mutation_bundle_says_which_commit_it_was_measured_on() -> None:
    """**「그때 빨개졌다」는 언제의 「그때」인지가 없으면 되짚을 수 없다** (감사 ⑪ NC-132).

    그 뒤에 코드가 바뀌면 적힌 빨강이 지금도 참인지 알 수 없는데, 커밋이 없으면
    **무엇이 바뀌었는지조차 물을 수 없다.** 실제로 묶음 둘이 커밋 없이 서 있었고,
    하필 그 둘이 그 회차가 재감사하던 줄들을 들고 있었다.

    **파일이 사라지는 것도 여기서 빨개진다.** 이 기록은 그 전까지 **아무것도 그것을
    지키지 않는** 파일이었다 — 통째로 지워도 초록이었다(감사 ⑪ OB-3). 그래서 전수
    단언에 앵커를 함께 건다: 훑을 것이 **있었다**는 것까지 센다(OB-1).

    **훑을 것을 낱말로 고르지 않는다** (감사 ⑮ NC-153). 처음에는 제목에 「고침」이
    든 절만 셌는데, 그러면 제목을 달리 지은 묶음이 **훑는 집합에 아예 들어오지
    않아** 커밋이 없어도 초록이다 — NC-132 가 낸 그 모양 그대로다. 어긋내 확인했다.
    묶음을 가르는 것은 제목의 문구가 아니라 **그 절이 표를 들고 있는가**이며, 이
    파일에서 표를 드는 절은 기록이고 들지 않는 절은 산문이다.

    **이 게이트가 못 보는 부류**(W-6 ③): 커밋이 적혀 있으나 **그 트리가 아닌**
    것 — 모양만 보고 값을 보지 않는다. 그리고 「`X` 뒤」처럼 **바탕**을 가리키는
    옛 형태도 통과한다. 둘 다 기계가 가를 수 없어 규칙이 산문으로 남는다.
    """
    assert _MUTATIONS.exists(), f"{_MUTATIONS} 가 없다 — 어긋냄의 기록이 사는 자리다"

    bundles = _bundles_with_a_table(_MUTATIONS.read_text())
    assert bundles, "표를 든 묶음이 하나도 없다 — 이 게이트가 아무것도 세지 않는다"

    anchorless = [
        f"docs/audit/mutations.md:{number} — {line.strip()}"
        for number, line in bundles
        if not _COMMIT.search(line)
    ]

    assert anchorless == [], "묶음이 어느 커밋에서 잰 것인지 말하지 않는다:\n" + "\n".join(
        anchorless
    )


def _table_rows(text: str) -> list[tuple[int, str]]:
    """표의 줄만 돌려준다 — 구분선(`|---|`)과 코드 블록 안은 뺀다."""
    rows: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        stripped = line.strip()
        if fenced or not stripped.startswith("|") or set(stripped) <= set("|-: "):
            continue
        rows.append((number, stripped))
    return rows


def _cells(row: str) -> int:
    """칸 수. 앞뒤의 구분자는 GFM 에서 선택이라 벗기고 센다.

    **이스케이프한 `\\|` 는 구분자가 아니다** (NC-157). GFM 은 그것을 칸 안의
    글자로 읽는데 여기서 함께 세면 **거짓 양성**이 난다 — 셀 안에 `||` 를 적은
    줄이 그 자리다. 게이트가 자기 사각으로 적어 둔 것이 실은 거짓 양성이었다.
    """
    return len(row.replace("\\|", "").strip("|").split("|"))


def test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare() -> None:
    """**선언한 열보다 셀이 많은 줄은 그 셀을 잃는다.**

    대장의 재감사 판정을 앞 셀에 잇지 않고 **칸 구분자 뒤에** 붙인 자리가 열둘
    있었고, 원문에서는 이어 보이는데 **렌더된 표에서는 사라진다**(NC-112).
    사람이 원문만 읽으면 끝까지 보이지 않는 부류라 기계가 센다.

    **이 게이트가 못 보는 부류**(W-6 ③): 셀이 **모자란** 줄(GFM 이 빈 칸으로
    채워 주므로 뜻이 사라지지는 않는다)과 **헤더 자체가 틀린** 표 — 셀 수만
    맞으면 통과한다. 이스케이프한 구분자는 **`_cells` 가 세지 않는다**(NC-157) —
    여기 「못 보는 것」으로 적혀 있었으나 실제로는 **거짓 양성**이었다.
    """
    overflowing = []
    for path in REPO_ROOT.rglob("*.md"):
        if ".venv" in path.parts or ".git" in path.parts:
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        width: int | None = None
        previous = 0
        for number, row in _table_rows(path.read_text()):
            if number != previous + 1:
                width = None  # 표가 끊겼다 — 다음 줄이 새 표의 머리다
            previous = number
            if width is None:
                width = _cells(row)
                continue
            if _cells(row) > width:
                overflowing.append(
                    f"{relative}:{number} — 머리는 {width} 칸인데 {_cells(row)} 칸이다"
                )

    assert overflowing == [], (
        "선언한 열보다 셀이 많다 — 넘치는 셀은 렌더에서 사라진다:\n" + "\n".join(overflowing)
    )
