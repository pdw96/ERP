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
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

import cmarkgfm
from cmarkgfm.cmark import Options

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


# `CLAUDE.md` 의 줄 천장. **한 자리에만 적는다** — 산문에 이 수를 베끼지 않는다
_CLAUDE_MD_CEILING = 250


def test_claude_md_stays_short() -> None:
    """**`CLAUDE.md` 는 매 세션 통째로 읽히는 입력물이다** — 길어지면 규칙이 묻힌다.

    2026-09-29 에 그 파일의 절반 넘게가 조각마다 쌓인 기록(「지금 어디인가」)이었다.
    기록은 `docs/지나온-길.md` 로, 리뷰를 처리할 때만 읽는 절은 `docs/리뷰-루프.md` 로
    옮겼다. 기록은 조각이 설 때마다 늘어나므로 **적어 두기만 해서는 다시 분다** —
    그래서 천장을 둔다. 넘으면 새 기록은 `docs/` 로, 특정 작업 때만 필요한 절은 그
    작업의 문서로 옮기고 여기에는 가리키는 줄만 남긴다.

    **이 게이트가 못 보는 부류**(W-6 ③): 천장 아래에서 기록이 규칙 사이에 섞여 드는 것,
    그리고 한 줄에 길게 몰아 쓰는 것 — 줄 수만 센다.
    """
    lines = (REPO_ROOT / "CLAUDE.md").read_text().splitlines()
    assert len(lines) <= _CLAUDE_MD_CEILING, (
        f"CLAUDE.md 가 {len(lines)} 줄이다(천장 {_CLAUDE_MD_CEILING}) — "
        "기록은 docs/ 로 옮기고 여기에는 가리키는 줄만 남긴다"
    )


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
    """표의 줄만 돌려준다 — 구분선(`|---|`)과 코드 블록 안은 뺀다.

    **대장(`docs/audit/README.md`) 전용이다.** 대장은 줄 머리의 울타리로만 코드 블록을
    연다(대장 게이트가 문다). 저장소 전체의 표는 GFM 파서가 가른다(`_overflowing_rows`).
    """
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
    """칸 수. 앞뒤의 구분자는 GFM 에서 선택이라 **하나씩만** 벗기고 센다.

    **이스케이프한 `\\|` 는 구분자가 아니다** (NC-157). GFM 은 그것을 칸 안의
    글자로 읽는데 여기서 함께 세면 **거짓 양성**이 난다 — 셀 안에 `||` 를 적은
    줄이 그 자리다. 게이트가 자기 사각으로 적어 둔 것이 실은 거짓 양성이었다.

    양끝의 `|` 를 모두 벗기면 `||a||` 가 한 칸이 된다 — GFM 은 한 개씩만 벗겨 세 칸으로
    읽는다(Codex 리뷰, ERP#18).
    """
    row = row.replace("\\|", "")
    row = row.removeprefix("|")
    row = row.removesuffix("|")
    return len(row.split("|"))


def _overflowing_rows(text: str) -> list[tuple[int, int, int]]:
    """GFM 이 **표로 렌더한** 본문 줄 가운데 머리보다 칸이 많은 줄 — (줄 번호, 머리, 그 줄).

    **표인지는 GitHub 의 파서(cmark-gfm)가 가른다.** 여기서 마크다운을 흉내 내면
    울타리 길이 · HTML 블록 · 목록 안 들여쓰기 · Setext 밑줄마다 틈이 났다 — ERP#18 의
    리뷰가 여섯 번 연달아 그 틈을 짚었다. 머리의 칸 수는 렌더된 `<th>` 로 세고, 본문 줄의
    칸 수는 파서가 알려 준 줄(`data-sourcepos`)의 원문에서 센다 — 넘친 칸은 렌더에서
    사라지므로 원문에서만 보인다.
    """
    # 원시 HTML 은 살리지 않는다 — 셀 안에 적은 `<th>` · `</table>` 이 파서가 만든 태그와 섞여
    # 칸 수를 부풀린다. 파서가 만든 태그에만 `data-sourcepos` 가 붙는다
    html = cmarkgfm.github_flavored_markdown_to_html(text, options=Options.CMARK_OPT_SOURCEPOS)
    # cmark 의 줄 끝은 `\n` · `\r\n` · `\r` 뿐이다 — `splitlines()` 는 U+2028 · 폼피드
    # 따위에서도 끊어, 그 뒤 표의 줄 번호가 파서와 어긋난다
    lines = re.split(r"\r\n|\r|\n", text)
    found = []
    for table in re.finditer(r"<table data-sourcepos=[^>]*>(.*?)</table>", html, re.S):
        head, _, body = table.group(1).partition("</thead>")
        width = len(re.findall(r"<th [^>]*data-sourcepos=", head))  # 정렬이면 `align` 이 앞선다
        for row in re.finditer(r'<tr data-sourcepos="(\d+):\d+-', body):
            number = int(row.group(1))
            # 본문 줄 앞에는 인용(`>`)과 공백만 온다 — 목록 표지가 오면 새 항목이다. 열 번호로
            # 자르지 않는다: 탭이 낀 컨테이너(`-\t`)에서 cmark 의 열은 바이트와 어긋난다
            source = lines[number - 1].lstrip(" \t>").rstrip()
            if _cells(source) > width:
                found.append((number, width, _cells(source)))
    return found


def test_a_table_row_does_not_carry_a_cell_the_header_did_not_declare() -> None:
    """**선언한 열보다 셀이 많은 줄은 그 셀을 잃는다.**

    대장의 재감사 판정을 앞 셀에 잇지 않고 **칸 구분자 뒤에** 붙인 자리가 열둘
    있었고, 원문에서는 이어 보이는데 **렌더된 표에서는 사라진다**(NC-112).
    사람이 원문만 읽으면 끝까지 보이지 않는 부류라 기계가 센다.

    **이 게이트가 못 보는 부류**(W-6 ③): 셀이 **모자란** 줄(GFM 이 빈 칸으로
    채워 주므로 뜻이 사라지지는 않는다)과 **헤더 자체가 틀린** 표 — 셀 수만
    맞으면 통과한다. 이스케이프한 구분자는 **`_cells` 가 세지 않는다**(NC-157) —
    여기 「못 보는 것」으로 적혀 있었으나 실제로는 **거짓 양성**이었다.

    **머리가 셈에서 빠져 있었다**(2026-09-29 까지). 줄을 손으로 가르면서 구분선이 만든 줄
    번호 틈을 표의 끊김으로 읽어, 첫 본문 줄이 머리 노릇을 했다 — `| a |` / `|---|` /
    `| b | c |` 가 통과했다. 이제 표는 파서가 가르고 머리는 렌더된 머리다(`_overflowing_rows`).
    """
    overflowing = [
        f"{path.relative_to(REPO_ROOT)}:{number} — 머리는 {width} 칸인데 {cells} 칸이다"
        for path in REPO_ROOT.rglob("*.md")
        if ".venv" not in path.parts and ".git" not in path.parts
        for number, width, cells in _overflowing_rows(path.read_text())
    ]

    assert overflowing == [], (
        "선언한 열보다 셀이 많다 — 넘치는 셀은 렌더에서 사라진다:\n" + "\n".join(overflowing)
    )


_LEDGER = REPO_ROOT / "docs" / "audit" / "README.md"

# 회차 기호. 범위를 적지 않는다 — 대장은 ⑳ 을 넘었고 기호는 유니코드에서 두 자리에
# 나뉘어 있다(아래 `_RUN_HEAD` 가 그 이유를 든다). 「⑦-b」처럼 꼬리가 붙는 회차가 있다.
_ROUND = re.compile(r"[①-⑳㉑-㉟㊱-㊿]")


# **대장의 코드 블록은 줄 머리(0 칸)의 울타리로만 연다** — 대장이 지키는 모양이다(아래
# `test_a_round_section_names_the_commit_it_audited` 가 다른 자리의 울타리를 막는다). 그래서
# 들여쓰기 · 인용 · 목록 안의 울타리를 가르지 않는다. 닫는 울타리는 같은 글자로 여는 것
# 이상 길고 뒤에 공백만 온다. 백틱 울타리의 꼬리에는 백틱이 없다(GFM)
_LEDGER_FENCE = re.compile(r"(`{3,}|~{3,})(.*)")


def _ledger_lines(text: str) -> Iterator[tuple[int, str, bool]]:
    """대장의 줄을 (번호, 줄, 코드 블록의 줄인가) 로 — 울타리 줄도 코드 블록의 줄이다.

    **닫히지 않은 블록은 실패다** — 문서 끝까지 코드로 삼켜 그 뒤의 절이 말없이 빠진다.
    """
    fence: tuple[str, int] | None = None
    opened_at = 0
    for number, line in enumerate(text.splitlines(), start=1):
        if fence is not None:
            char, length = fence
            if re.fullmatch(rf"{re.escape(char)}{{{length},}}[ \t]*", line):
                fence = None
            yield number, line, True
            continue
        opened = _LEDGER_FENCE.fullmatch(line)
        if opened and (opened.group(1)[0] == "~" or "`" not in opened.group(2)):
            fence = (opened.group(1)[0], len(opened.group(1)))
            opened_at = number
            yield number, line, True
            continue
        yield number, line, False
    assert fence is None, f"대장 {opened_at} 줄에서 연 코드 블록이 닫히지 않았다"


def _rounds_with_a_section(text: str) -> set[str]:
    """회차 절이 선 회차들 — `## 감사 ⑬(...)` 의 기호만 센다. 코드 블록 안은 절이 아니다."""
    return {
        found
        for _, line, in_code in _ledger_lines(text)
        if not in_code and line.startswith("## 감사 ")
        for found in _ROUND.findall(line)
    }


# 회차별 W 표의 첫 칸은 **회차 이름뿐**이다 — `⑪` · `⑦-b` · `⑧ 셋` 꼴.
# **「로 시작한다」로 고르면 안 된다**: 「아직 아무도 보지 않은 것」 표에도
# `⑰ 이 고친 자리(…)` 처럼 회차 기호로 시작하는 행이 있어, 그것까지 세면
# **회차별 W 표에서 줄을 지워도 게이트가 통과한다**(어긋내 확인했다).
_ROUND_LABEL = re.compile(r"[①-⑳㉑-㉟㊱-㊿](?:-b)?(?:\s+[가-힣]{1,3})?\Z")


def _rounds_in_the_round_table(text: str) -> set[str]:
    """회차별 W 표에 줄이 있는 회차들 — 첫 칸이 **회차 이름뿐인** 행만 센다."""
    found: set[str] = set()
    for _, row in _table_rows(text):
        first = row.strip("|").split("|")[0].strip()
        if _ROUND_LABEL.fullmatch(first):
            found.update(_ROUND.findall(first))
    return found


def test_a_round_that_closed_leaves_a_line_in_the_round_table() -> None:
    """**회차를 닫는 사람이 회차별 W 표에 줄을 적는다** (감사 ⑱ — NC-142 의 다섯째).

    같은 자리가 NC-49 → 57 → 93 → 142 → 이번으로 **다섯 번** 깨졌다. 네 번째
    뒤에 세는 방법을 바꿨는데(눈으로 세지 않고 기한 칸에서 뽑는다) 또 멈췄다 —
    **적는 시점이 여전히 사람**이었고 ⑬ 부터 다섯 회차가 줄 없이 지나갔다.
    이 저장소의 규칙은 「같은 규칙이 세 번 이상 깨졌으면 자동 게이트로 설 수
    있는지 묻는다」이고, 이것은 **기계가 셀 수 있는 모양**이다.

    **수를 세지 않는다.** 회차 절이 선 기호와 표에 줄이 있는 기호를 **집합으로**
    견준다 — 회차가 하나 늘어도 이 검사는 낡지 않는다(NC-86).

    **이 게이트가 못 보는 부류**(W-6 ③): 줄은 있는데 **내용이 틀린** 것
    (⑦-b 행이 아홉을 여덟으로 적었던 자리 — NC-93 — 가 그 부류다), 꼬리로만 갈리는
    회차(`⑦` 과 `⑦-b` 는 같은 기호라 한 줄로 센다), 그리고 **절도 줄도 없이
    지나간** 회차 — 그것은 이 파일이 아니라 대장 자신이 모르는 회차다.
    """
    ledger = _LEDGER.read_text()
    tabled = _rounds_in_the_round_table(ledger)
    assert tabled, "회차별 W 표를 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    # **표가 시작한 자리부터 센다.** 그 표는 ⑤ 무렵에 섰고 앞 회차들에는 줄이
    # 없다 — 회차 기록은 소급해 고치지 않으므로(대장이 그렇게 정했다) 그 앞은
    # 이 게이트의 대상이 아니다. 바닥을 **표 자신**에서 읽으므로 손으로 적은
    # 예외 목록이 생기지 않는다.
    floor = min(tabled)
    missing = sorted(
        round_
        for round_ in _rounds_with_a_section(ledger)
        if round_ >= floor and round_ not in tabled
    )

    assert missing == [], (
        "회차 절은 있는데 회차별 W 표에 줄이 없다 — 회차를 닫는 사람이 적는다:\n"
        + "\n".join(f"  감사 {round_} 절은 있고 표에 줄이 없다" for round_ in missing)
    )


# **감사한 커밋을 적지 않은 회차 절들.** ① ~ ⑬ 은 절마다 `감사한 커밋` 줄을 두었는데
# ⑭ 부터 여섯 절이 그 줄 없이 지나갔다 — 적는 사람이 잊었고 아무것도 묻지 않았다.
# 회차 기록은 소급해 고치지 않으므로(대장이 그렇게 정했다) **절의 머리 그대로** 둔다 —
# 회차 기호로 두면 같은 기호의 새 절(`⑭-b`)까지 풀려난다.
# **예외가 늘면 이 목록이 diff 에 보인다.**
_NO_COMMIT_LINE = {
    "## 감사 ⑭(`audit-data`) — ⑩ 의 고침 셋 재감사 (2026-09-22)": "소급해 고치지 않는다",
    "## 감사 ⑮(`audit-quality`) — ⑪ 의 고침 둘 재감사 (2026-09-22)": "소급해 고치지 않는다",
    "## 감사 ⑯(`audit-contract`) — ⑫ 와 Codex 의 계약 고침 다섯 재감사 (2026-09-22)": (
        "소급해 고치지 않는다"
    ),
    "## 감사 ⑰(`audit-ops`) — ⑬ 과 Codex 의 운영 고침 셋 재감사 (2026-09-22)": (
        "소급해 고치지 않는다"
    ),
    "## 감사 ⑱(`audit-internal`) — ⑫ 의 고침 아홉 재감사 + ⑭~⑰ 의 새 산문 (2026-09-22)": (
        "소급해 고치지 않는다"
    ),
    "## 감사 ⑲(`audit-secrets`) — ⑧ 이후 처음 (2026-09-22)": "소급해 고치지 않는다",
}
# 절이 **여는** 줄 — 몸의 첫 줄이 이것이어야 한다. 몸 어딘가에 있는 것으로는 모자란다:
# 인용한 예(`> - **감사한 커밋**: …`)나 산문 뒤의 줄은 다음 회차가 기준을 고르는 자리가 아니다
# 짧은 SHA 의 길이는 `core.abbrev` 가 정한다(4 까지 줄어든다). SHA-256 저장소면 64 까지 길다
_COMMIT_LINE = re.compile(r"- \*\*감사한 커밋\*\*: `[0-9a-f]{4,64}`")
# 감사를 **돌린** 절의 머리 — `감사 ⑧(audit-data) —` · `감사 ⑤-b —` 꼴. `감사 ⑧ 의 번호 대조`
# 처럼 회차를 가리키기만 하는 절은 감사를 돌린 것이 아니다. 기호는 ⑳ 에서 끝나지 않는다 —
# ㉑ ~ ㉟ · ㊱ ~ ㊿ 은 유니코드에서 다른 자리에 있어, 빠뜨리면 그 절을 **말없이** 건너뛴다
_RUN_HEAD = re.compile(r"## 감사 [①-⑳㉑-㉟㊱-㊿](?:-b)?(?:\(| —)")
# **대장이 지키는 모양.** 마크다운의 변형을 가르지 않고, 가르지 않은 모양이 **대장에 없게**
# 한다 — 그 안의 머리가 절로 세이거나 빠지는 틈이 곧 이 게이트의 틈이다. 그래서 컨테이너를
# 해석하지 않고 **글자로** 본다: 인용 · 목록 경계의 평범한 가로줄도 막힌다(가로줄 위에는
# 빈 줄을 둔다). 대장은 지금 넷 다 쓰지 않는다(2026-09-29).
# 코드 블록 밖의 울타리 글자 — 줄 머리가 아닌 울타리(들여쓰기 · 인용 · 목록 안)는 코드 블록을
# 열어 그 몸이 머리로 읽히거나 빠진다
_FENCE_CHARS = re.compile(r"`{3,}|~{3,}")
# 감사 머리의 꼴 — 줄 머리의 `## 감사 ` 가 아니면 렌더되는데 셈에서 빠진다(들여쓰기 · 인용 ·
# 목록 안 · 다른 수준)
_ANY_ROUND_HEAD = re.compile(r"#[ \t]*감사[ \t]*[①-⑳㉑-㉟㊱-㊿]")
# 꾸민 감사 머리(`## **감사 ㉑** —`) — 머리 줄에서 꾸밈 글자를 빼고 보이는 글이 「감사 + 회차
# 기호」로 시작하면 감사 머리다. 줄 머리의 `## 감사 ` 가 아니면 절로 세이지 않는다
_HEADING = re.compile(r"[ >\t]*(?:(?:[-*+]|\d{1,9}[.)])[ >\t]*)?#{1,6}(?:[ \t]|$)")
_DECORATION = re.compile(r"[*_`~\[\]()<>\\]")
_ROUND_TEXT = re.compile(r"[ \t]*감사[ \t]*[①-⑳㉑-㉟㊱-㊿]")
# HTML — 주석 · 태그 속의 `## ` 는 렌더되지 않는다. 줄 머리 · 목록 · 문장 가운데 어디든
# 태그(`<em>` · `</em>`) · 주석 · 처리 지시 · 선언을 찾는다. 인라인 코드(`` `<SHA>` ``)는
# 글자라 먼저 지운다. 자동 링크(`<https://…>`)는 태그 이름 뒤에 `:` 가 와서 걸리지 않는다
_HTML = re.compile(
    r"<(?:[A-Za-z][A-Za-z0-9-]*(?=[\s/>]|$)|/[A-Za-z][A-Za-z0-9-]*[ \t]*>|!--|\?|!)"
)
# 인라인 코드 — 백틱 하나로 여닫는 것만 지운다. 이스케이프한 백틱(`\``)이나 겹 백틱이 있는 줄은
# 코드 스팬을 가르지 않고 원문을 본다(넓게 막는다 — 인라인 코드 속 `<…>` 는 백틱 하나로 감싼다)
_CODE_SPAN = re.compile(r"`[^`]*`")
# Setext 머리의 밑줄 — 글자가 있는 줄 바로 아래의 `---` · `===` 는 그 줄을 머리로 만든다
_UNDERLINE = re.compile(r"[ >\t]*(?:=+|-+)[ \t]*")


def _round_sections(text: str) -> list[tuple[str, str]]:
    """감사를 돌린 `## 감사 …` 절마다 (머리 줄, 몸의 첫 줄) — 빈 줄은 건너뛴다.

    **코드 블록 안의 `## ` 는 머리가 아니다** — 대장이 양식을 보이려고 적은 예가 절로
    세이면 예가 떨어지거나, 예외의 머리를 인용한 예가 낡은 예외를 붙잡아 둔다.
    """
    sections: list[tuple[str, str]] = []
    head: str | None = None
    for _, line, in_code in _ledger_lines(text):
        if in_code:
            if head is not None:  # 절이 코드 블록으로 열리면 그 울타리가 첫 줄이다
                sections.append((head, line))
                head = None
            continue
        if line.startswith("## "):
            if head is not None:
                sections.append((head, ""))
            head = line if _RUN_HEAD.match(line) else None
        elif head is not None and line.strip():
            sections.append((head, line))
            head = None
    if head is not None:
        sections.append((head, ""))
    return sections


def _off_contract(text: str) -> list[str]:
    """대장이 지키는 모양을 벗어난 줄 — 코드 블록 안은 보지 않는다."""
    lines = list(_ledger_lines(text))
    found = []
    for number, line, in_code in lines:
        if in_code:
            continue
        if _FENCE_CHARS.search(line):
            found.append(
                f"  {number}: 코드 블록은 줄 머리의 울타리로만 연다 — 다른 자리에 쓰지 않는다"
            )
        heading = _HEADING.match(line)
        formatted = heading and _ROUND_TEXT.match(_DECORATION.sub("", line[heading.end() :]))
        if (_ANY_ROUND_HEAD.search(line) or formatted) and not line.startswith("## 감사 "):
            found.append(f"  {number}: 감사 머리는 줄 머리의 `## 감사 ` 로 쓴다")
        plain = line if "\\`" in line or "``" in line else _CODE_SPAN.sub("", line)
        if _HTML.search(plain):
            found.append(f"  {number}: HTML 을 두지 않는다")
    found += [
        f"  {number}: 글자 있는 줄 바로 아래에 `---` · `===` 를 두지 않는다 — 위를 비운다"
        for (_, above, above_code), (number, line, in_code) in pairwise(lines)
        if not (above_code or in_code) and above.strip(" >\t") and _UNDERLINE.fullmatch(line)
    ]
    return found


def test_a_round_section_names_the_commit_it_audited() -> None:
    """**회차 절은 감사한 커밋으로 연다** — 다음 회차의 기준이 그 SHA 다.

    브리핑 보관본(`.claude/briefs/`)은 `.gitignore` 에 있어 저장소에 남지 않으므로
    「그 회차가 어느 커밋을 봤는가」는 대장의 이 줄에만 남는다. ⑭ 부터 여섯 절이
    적지 않았고, ⑲ 다음 회차의 기준을 판정 커밋의 부모로 **짐작해야** 했다
    (2026-09-29, `/audit-brief` 실사용 시험). 적는 규칙은 ① 부터 있었다 — 지키는
    것이 사람뿐이라 끊겼다.

    **이 게이트가 못 보는 부류**(W-6 ③): 줄은 있는데 **SHA 가 틀린** 것 — 그 회차가
    실제로 본 커밋인지는 브리핑과 견줘야 하고, 브리핑은 저장소에 없다. 그리고
    `## 감사 ` 로 시작하되 위 머리 꼴을 벗어난 절 — 그런 절은 감사를 돌린 절로 세지 않는다.
    브리핑에 커밋 안 된 변경이 들었는데 줄 끝의 `· 커밋 안 된 변경 포함` 이 빠진 것도
    못 본다 — 그 역시 브리핑과 견줘야 안다(빠져도 다음 회차는 그 SHA 부터 다시 볼 뿐이다).

    **마크다운을 해석하지 않는다.** 인용 · 목록 · Setext · HTML 을 가르는 해석기를 여기 세웠다가
    리뷰마다 새 틈이 났다(ERP#17, 2026-09-29). 대신 가르지 않는 모양이 대장에 **없게** 한다 —
    넓게 막아 평범한 문장이 걸릴 수 있고, 그러면 문장을 고친다.
    """
    ledger = _LEDGER.read_text()
    off = _off_contract(ledger)
    assert off == [], "대장이 이 게이트가 가르는 모양을 벗어났다:\n" + "\n".join(off)

    sections = _round_sections(ledger)
    assert sections, "회차 절을 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    missing = [
        head
        for head, first in sections
        if not _COMMIT_LINE.match(first) and head not in _NO_COMMIT_LINE
    ]
    assert missing == [], (
        "회차 절의 첫 줄이 「- **감사한 커밋**: `<SHA>`」가 아니다 — "
        "브리핑의 「대상」 SHA 로 연다:\n" + "\n".join(f"  {head}" for head in missing)
    )

    # 예외는 **그 한 절**의 것이다 — 같은 머리가 두 번이면 새 절이 옛 예외에 묻어 간다
    stale = sorted(
        head
        for head in _NO_COMMIT_LINE
        if [h for h, _ in sections].count(head) != 1
        or any(_COMMIT_LINE.match(first) for h, first in sections if h == head)
    )
    assert stale == [], (
        "예외 목록의 절이 사라졌거나, 둘이 되었거나, 이제 감사한 커밋으로 연다:\n"
        + "\n".join(f"  {head}" for head in stale)
    )


# 「아직 아무도 보지 않은 것」 표가 기다리는 NC 를 드는 꼴 — `⑱ 이 고친 자리(142 · 166 ~ 171)`
_WAITING = re.compile(r"(?:고친|낸) 자리\(([^)]*)\)|NC-(\d+)")
_NC_SPAN = re.compile(r"(\d+)(?:\s*~\s*(\d+))?")


def _section(text: str, head: str) -> str:
    """`## <head>` 절의 몸 — 다음 `## ` 머리 앞까지."""
    start = text.index(f"\n## {head}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _row_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().removeprefix("|").removesuffix("|").split("|")]


def _closed_ncs(text: str) -> set[int]:
    closed: set[int] = set()
    for _, row in _table_rows(_section(text, "부적합 대장")):
        cells = _row_cells(row)
        if cells[0].isdigit() and cells[4].startswith("**닫힘"):
            closed.add(int(cells[0]))
    return closed


def _waiting_on(cell: str) -> set[int]:
    named: set[int] = set()
    for group, single in _WAITING.findall(cell):
        for low, high in _NC_SPAN.findall(group or single):
            named.update(range(int(low), int(high or low) + 1))
    return named


def test_a_row_still_waiting_does_not_wait_on_a_closed_nc() -> None:
    """**「아직 아무도 보지 않은 것」 표가 이미 닫힌 NC 를 기다리지 않는다** (감사 ㉓ — NC-179).

    NC-142 는 「**두 표**가 지나간 회차를 모른다」였는데 게이트는 회차별 W 표 하나에만
    섰고, 그 뒤 이 표가 ⑫ · ⑲ 가 닫은 줄을 「아직 기다린다」로 든 채 남았다 — 같은
    자리의 여섯째다. 사람이 적는 쪽이 또 멈췄으므로 이쪽도 기계가 센다.

    **닫는 것은 재감사다**(대장 「닫는 규칙」). 그러니 **담당이 하나인 줄에서** 첫 칸이
    드는 NC 가운데 하나라도 닫혔으면 그 재감사는 **이미 돌았고**, 줄은 지운 줄(`~~…~~`)이
    되어 결과를 적어야 한다. 수를 세지 않고 번호의 **집합**을 견준다 — 대장이 자라도
    낡지 않는다(NC-86).

    **이 게이트가 못 보는 부류**(W-6 ③): 첫 칸이 「…이 고친 자리(…)」 · 「…이 낸
    자리(…)」 · `NC-N` 꼴이 아닌 줄, **셋째 칸의 산문**이 든 번호(「… 는 아직 기다린다」),
    이미 지운 줄의 낡은 문장, 그리고 재감사 없이 닫히는 「갈래 추가」(대장 머리) — 그
    번호가 닫혔어도 재감사는 돌지 않았으므로 이 게이트는 거짓 양성을 낸다. 그때는 줄을
    지우지 말고 그 번호를 첫 칸에서 뺀다.

    **담당이 여럿인 줄도 거짓 양성을 낸다**(감사 ㉔ — NC-185). 한 담당이 제 몫을 닫아도
    다른 담당은 아직 기다린다 — 대장의 ⑧ 셋 행과 ⑫ 행이 그랬다. 그 줄을 지우면 남은
    담당의 재감사가 표에서 사라지므로, **줄을 담당별로 나눈다**. 닫은 담당의 줄은 지운
    줄이 되고, 남은 담당의 줄은 제 몫의 번호만 든다.
    """
    ledger = _LEDGER.read_text()
    closed = _closed_ncs(ledger)
    assert closed, "부적합 대장에서 닫힌 줄을 찾지 못했다 — 이 게이트가 아무것도 견주지 않는다"

    waiting = _section(ledger, "아직 아무도 보지 않은 것")
    rows = [_row_cells(row) for _, row in _table_rows(waiting)]
    live = [cells[0] for cells in rows[1:] if not cells[0].startswith("~~")]
    assert any(_waiting_on(first) for first in live), (
        "기다리는 NC 를 드는 줄을 찾지 못했다 — 이 게이트가 아무것도 견주지 않는다"
    )

    stale = [
        f"  {first[:60]} … — 닫힌 NC {sorted(_waiting_on(first) & closed)}"
        for first in live
        if _waiting_on(first) & closed
    ]
    assert stale == [], (
        "「아직 아무도 보지 않은 것」의 살아 있는 줄이 이미 닫힌 NC 를 기다린다 — "
        "재감사가 돌았으면 줄을 지우고 결과를 적는다(담당이 여럿이면 줄을 담당별로 나눈다):\n"
        + "\n".join(stale)
    )
