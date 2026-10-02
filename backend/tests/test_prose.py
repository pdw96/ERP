"""산문을 무는 게이트 — **적어 두기만 하고 강제하지 않는 규칙을 만들지 않는다.**

**이 머리는 이 파일이 생긴 유래다 — 파일에 든 게이트의 목록이 아니다**(저장소 소유자가
정했다, 2026-09-30 — 감사 ㉓ OB-6). 뒤에 선 게이트는 각자의 독스트링이 제 유래를 든다.

`CLAUDE.md` 가 규칙 셋을 들고 있는데 셋 다 지키는 것이 사람뿐이었다 — 그 상태로
통과한 결함이 대장에서 **가장 큰 무리**다. 처음 선 둘은 이것을 기계에 옮겼다.

1. **단계 표기는 사실이 바뀔 때 함께 고친다** — 닫힌 단계를 「…에」로 가리키는
   현재형 문장은 그 단계가 끝나는 순간 거짓이 된다
2. **화면을 만들지 않는다** — `CLAUDE.md` 「금지」(2단계의 성공기준이 처음 요구했다)

**셋째(수)는 게이트를 세우지 않는다.** 「테스트 N개」류는 무는 것보다 **지우는
쪽**이 답이고(`CLAUDE.md` 「될 수 있으면 적지 말고 목록을 가리킨다」), 실제로 NC-59
가 그 답을 냈다 — 세지 않는 문장으로 바꾸는 것.

> **이 게이트가 못 보는 부류**(W-6 ③ — 가드는 자기가 못 보는 것을 적는다):
> 아래 `_RECORDS` 에 통째로 빠진 파일 안에서 새로 나는 자리, 조사 없이
> 「1단계」만 쓴 문장, 그리고 **닫히지 않은 단계**에 대한 거짓 주장. 마지막
> 것은 기계가 가를 수 없다 — 그 단계가 아직 진행 중이면 참일 수 있다.
"""

import re
import subprocess
from collections import Counter
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
# 않으므로 단계가 닫히는 날 이 게이트가 저절로 넓어진다 — 2단계가 닫힐 때 그랬다.
_CLOSED_RECORD = re.compile(r"PRD-(\d+)단계\.md$")

# **기록이라 소급해 고치지 않는 자리.** 예외가 늘면 이 목록이 diff 에 보인다.
_RECORDS = {
    "docs/PRD-1단계.md": "닫힌 기록 — 그 문서가 스스로 그렇게 적는다",
    "docs/PRD-2단계.md": "닫힌 기록 — 그 문서가 스스로 그렇게 적는다",
    "docs/audit/README.md": "회차 기록은 소급해 고치지 않는다 — 대장이 그렇게 정했다",
    "docs/audit/회차-기록.md": "대장의 지나간 쪽 — 회차 절과 닫힌 줄이 옮겨 갔다(ADR 0010)",
}

# **줄 단위 예외.** 과거형이거나, 규칙이 자기 예를 드는 줄이다.
_ALLOWED = {
    ("CLAUDE.md", "단계 표기는 사실이 바뀔 때"): "규칙이 자기 표기를 예로 든다",
    ("tests/test_prose.py", "그 단계가 끝나는 순간 거짓이"): "게이트가 자기 예를 든다",
    ("docs/audit/mutations.md", "로 되돌렸다"): "어긋낸 문장을 그대로 인용한 기록",
    ("docs/schema.md", "두지 않기로 했다"): "과거형 — 결정의 기록",
    ("docs/schema.md", "두지 않기로 정한 것"): "과거형 — 결정의 기록",
}


def _repo_files(pattern: str) -> list[Path]:
    """**git 이 드는 파일만** — 추적하는 것과, 추적 안 됐으나 무시되지 않는 것(감사 ㉗ NC-202).

    처음에는 `rglob` 로 모으고 `.venv` · `.git` 만 뺐다. 그러면 `.gitignore` 에 든 브리핑 보관본
    (`.claude/briefs/`)까지 읽혀, 보관본이 diff 로 담은 `CLAUDE.md` 의 줄이 예외 목록을 벗어난
    경로에서 다시 나타났다 — 감사를 돌린 작업트리에서만 빨갛고 CI 에서는 초록이라 **로컬과
    CI 가 갈렸다.** 커밋될 수 있는 파일은 git 이 안다. 추적 안 된 새 파일도 들이므로
    `git add` 전에도 문다.

    닫힌 단계를 **찾는** 자리도 이것으로 모은다 — 무시된 워크트리에 뒤 단계의 `PRD-N단계.md` 가
    있으면 그 단계를 닫힌 것으로 읽어 추적하는 산문이 빨개졌다(PR #38 Codex 리뷰).

    **이 선택이 못 보는 부류**(W-6 ③): `.gitignore` 에 잘못 든 파일 — 무시되면 이 게이트들도
    보지 않는다. git 이 없는 자리에서는 돌지 않고 실패한다(건너뛰지 않는다).
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", pattern],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode()
    return [
        path for name in listed.split("\0") if name and (path := REPO_ROOT / name).is_file()
    ]


def _tracked() -> list[Path]:
    found: list[Path] = []
    for pattern in _PROSE:
        found += _repo_files(pattern)
    return found


def test_a_stage_that_closed_is_not_written_as_if_it_were_now() -> None:
    """**닫힌 단계를 현재형으로 가리키지 않는다.**

    「1단계에서는 표만 선다」는 그 단계가 끝나는 순간 거짓이 되는데 아무것도
    물지 않았다 — NC-60 이 네 자리를 주웠고 그 전수가 코드가 아니라 사람이라
    **다섯째가 남아 있었다**(NC-92). 여기서부터는 기계가 센다.
    """
    closed = {
        match.group(1)
        for path in _repo_files("docs/PRD-*단계.md")
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
    """**화면을 만들지 않는다** — `CLAUDE.md` 「금지」가 이것을 요구한다.

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


# 두 스키마 문서의 표 번호 — 「표 N」 · 「§N」. 「N번」은 「N 회」와 겹쳐 세지 않고,
# 「표 N개」는 수라 번호가 아니다
# 「표」 앞에 한글이 붙으면 다른 낱말의 끝이다(「대표 1명」 — PR #39 Codex 리뷰)
_TABLE_NUMBER = re.compile(r"(?<![가-힣])(?:표|§)\s?\d{1,2}(?!\d|\s?개)")
_SCHEMA_DOCUMENTS = ("schema.md", "schema-2단계.md")

# 번호를 문서 이름 없이 써도 되는 파일 — 이름과 사유로 든다
_TABLE_NUMBER_OWNERS = {
    "docs/schema.md": "번호의 주인 — 자기 표를 번호로 부른다",
    "docs/schema-2단계.md": "번호의 주인 — 자기 표를 번호로 부른다",
    "docs/audit/README.md": "감사 기록 — 이 규칙 앞의 문장을 고치지 않는다",
    "docs/audit/회차-기록.md": "감사 기록 — 대장에서 옮겨 간 옛 문장(ADR 0010)",
    "docs/audit/mutations.md": "어긋냄 기록 — 규칙을 어긴 글자를 어긋냄으로 옮겨 적는다",
}


def test_a_third_document_names_the_schema_document_with_a_table_number() -> None:
    """**제3 문서는 두 스키마 문서의 표를 문서 이름 없이 번호로 부르지 않는다** (㉘ NC-206).

    두 문서의 번호 체계가 어긋나 있어 문서 이름 없는 번호는 잘못 따라가도 그럴듯하게 읽힌다 —
    규칙은 `docs/schema-2단계.md` 머리가 든다. 지키는 것이 사람뿐이라 같은 모양이 NC-139 · 170 ·
    ㉓ OB-3 · NC-200 으로 넷째까지 났고, 매번 사람이 한 자리씩 주웠다. 번호가 든 줄에 두 문서
    가운데 하나의 이름이 **같은 줄에** 있어야 한다.

    **이 게이트가 못 보는 부류**(W-6 ③): 「N번」 꼴(「N 회」와 겹쳐 세지 않는다), 문서 이름이
    **앞 줄에** 있는 것(그때는 거짓 양성이다 — 같은 줄로 옮긴다), 그리고 다른 번호 체계(ADR ·
    NC · 회차)를 쓰면서 「표」라는 낱말을 붙인 것 — 그 모양은 거짓 양성이 된다. 그리고
    `_TABLE_NUMBER_OWNERS` 가 **통째로** 빼는 파일 안의 줄이다(감사 ㉙ NC-215, 어긋내
    확인했다) — 두 스키마 문서가 서로의 표를 번호로 부르는 것(위에 든 NC-139 · 170 이 바로 그
    모양이다), 그리고 규칙 **뒤에** 대장 · `mutations.md` 에 새로 쓰는 줄. 이름이 같은 줄에
    **있는지만** 보므로, 같은 줄의 문서 이름이 **틀린** 것(「`docs/schema.md` 의 표 18」)도 못
    본다.
    """
    files = [
        path
        for path in _repo_files("*")
        if path.relative_to(REPO_ROOT).as_posix() not in _TABLE_NUMBER_OWNERS
    ]
    assert files, "훑을 파일이 없다 — 이 게이트가 아무것도 세지 않는다"

    bare = []
    for path in files:
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if _TABLE_NUMBER.search(line) and not any(
                name in line for name in _SCHEMA_DOCUMENTS
            ):
                bare.append(
                    f"  {path.relative_to(REPO_ROOT).as_posix()}:{number} — {line.strip()}"
                )

    assert bare == [], (
        "두 스키마 문서의 표를 문서 이름 없이 번호로 부른다 — 이름(`stock_ledger_entries` "
        "처럼)으로 부르거나 같은 줄에 문서 이름을 적는다:\n" + "\n".join(bare)
    )


_MUTATIONS = REPO_ROOT / "docs/audit/mutations.md"

# 아직 초록인 어긋냄을 모으는 절(감사 ㉕ OB-1). 묶음이 아니라 **묶음을 가리키는 색인**이라
# 잰 커밋이 없고, 셋째 칸도 「빨개진 검사」가 아니다 — 묶음을 훑는 게이트는 이 절의
# **색인 표만** 뺀다(`_mutation_bundles`). 처음에는 절을 통째로 뺐다(감사 ㉘ NC-205 · ㉙ NC-216)
_STILL_GREEN = "아직 초록인 어긋냄"


def _mutation_bundles() -> str:
    """`mutations.md` 에서 「아직 초록인 어긋냄」의 **색인 표**를 뺀 것 — 어긋냄 묶음만 남는다.

    처음에는 절을 통째로 뺐는데, 그러면 그 절과 다음 `## ` 사이에 `###` 로 둔 묶음이 커밋이
    없어도, 초록 줄이 색인에 없어도 모든 게이트를 지났다(감사 ㉘ NC-205, 어긋내 확인했다). 이제
    머리가 `기록` 으로 여는 표의 줄만 빈 줄로 바꾼다 — 줄 번호도 원문과 같게 남는다.
    """
    lines = _MUTATIONS.read_text().split("\n")
    start = lines.index(f"## {_STILL_GREEN}")
    head = next(
        number for number in range(start, len(lines)) if lines[number].startswith("| 기록 |")
    )
    end = head
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return "\n".join(lines[:head] + [""] * (end - head) + lines[end:])


# 묶음 제목이 드는 커밋. 이 파일의 관용구가 백틱이라 백틱까지 본다 — 맨 글자만
# 세면 산문 속의 우연한 16진 토막이 통과시킨다.
_COMMIT = re.compile(r"`[0-9a-f]{7,40}`")

# 칸 구분자 — 이스케이프한 `\\|` 는 칸 안의 글자다(NC-157)
_UNESCAPED_BAR = re.compile(r"(?<!\\)\|")


# 제목 줄 — 수준을 가리지 않는다(감사 ㉕ NC-186). 대장의 W 표 절을 자르는 데 쓴다
_ANY_HEADING = re.compile(r"#{1,6} ")


def _bundles_with_a_table(text: str) -> list[tuple[int, str]]:
    """**표마다** 그 표 바로 위의 가장 가까운 제목을 돌려준다 — 표가 어긋냄의 기록이다.

    제목의 문구에 기대지 않는 이유는 아래 게이트의 독스트링에 있다(NC-153). 제목의
    **수준**에도 기대지 않는다(NC-186) — `## ` 만 보면 `###` 묶음과 한 절의 둘째 표가
    훑는 집합 밖에 섰다. 위에 제목이 없는 표는 그 표의 첫 줄을 제목 자리에 둔다 —
    커밋이 없으니 빨갛다.

    **표와 제목은 GitHub 의 파서(cmark-gfm)가 가른다**(감사 ㉗ NC-195). 줄 머리 글자로
    가르면 앞 파이프를 뺀 표 · 인용 안의 표 · 목록 안의 표가 훑는 집합에 아예 들어오지
    않았고(어긋내 확인했다), Setext 제목은 제목으로 보이지 않았으며, 울타리 코드 안의 `#`
    줄은 제목으로 읽혀 뒤 표에 커밋을 빌려주었다. `_overflowing_rows` 와 같은 방식이다 —
    파서가 알려 준 시작 줄(`data-sourcepos`)의 원문을 제목으로 읽는다.
    """
    html = cmarkgfm.github_flavored_markdown_to_html(text, options=Options.CMARK_OPT_SOURCEPOS)
    lines = re.split(r"\r\n|\r|\n", text)
    blocks = sorted(
        (int(found.group(2)), found.group(1))
        for found in re.finditer(r'<(h[1-6]|table) data-sourcepos="(\d+):', html)
    )
    found: list[tuple[int, str]] = []
    heading: tuple[int, str] | None = None
    for number, tag in blocks:
        if tag.startswith("h"):
            heading = (number, lines[number - 1])
        else:
            found.append(heading if heading is not None else (number, lines[number - 1]))
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
    묶음을 가르는 것은 제목의 문구가 아니라 **표**이며, 이 파일에서 표는 기록이고
    표가 아닌 것은 산문이다. **표마다 바로 위의 제목**을 본다 — 처음에는 `## ` 절의
    첫 표만 셌는데, 그러면 `###` 묶음과 한 절에 덧붙인 둘째 표가 커밋 없이도 초록이었다
    (감사 ㉕ NC-186, 어긋내 확인했다).

    표와 제목은 파서가 가른다 — 줄 머리 글자로 가르던 때는 앞 파이프 없는 표와 인용 안의
    표가 훑는 집합 밖이었다(감사 ㉗ NC-195, 어긋내 확인했다).

    **이 게이트가 못 보는 부류**(W-6 ③): 커밋이 적혀 있으나 **그 트리가 아닌**
    것 — 모양만 보고 값을 보지 않는다. 그리고 「`X` 뒤」처럼 **바탕**을 가리키는
    옛 형태도 통과한다. 둘 다 기계가 가를 수 없어 규칙이 산문으로 남는다. **옛 절
    밑에 나중에 덧붙인 표**도 그 절 제목의 커밋을 빌려 통과한다 — 새로 잰 것은 새
    제목 아래에 둔다.
    """
    assert _MUTATIONS.exists(), f"{_MUTATIONS} 가 없다 — 어긋냄의 기록이 사는 자리다"

    bundles = _bundles_with_a_table(_mutation_bundles())
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

    **대장(`docs/audit/` 의 `README.md` · `회차-기록.md`) 전용이다.** 대장은 줄 머리의
    울타리로만 코드 블록을 연다(대장 게이트가 문다). 저장소 전체의 표는 GFM 파서가
    가른다(`_overflowing_rows`).
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
        for path in _repo_files("*.md")
        for number, width, cells in _overflowing_rows(path.read_text())
    ]

    assert overflowing == [], (
        "선언한 열보다 셀이 많다 — 넘치는 셀은 렌더에서 사라진다:\n" + "\n".join(overflowing)
    )


_LEDGER = REPO_ROOT / "docs" / "audit" / "README.md"
# **대장의 지나간 쪽**(ADR 0010) — 닫힌 줄의 표와 회차 절, 회차별 W 표(감사 ⑥ 절 안)가
# 여기 산다. 대장을 읽는 게이트는 두 파일을 함께 읽는다 — 한쪽만 읽으면 옮겨 간 쪽의 줄이
# 말없이 빠진다
_LEDGER_RECORD = REPO_ROOT / "docs" / "audit" / "회차-기록.md"
_LEDGER_FILES = (_LEDGER, _LEDGER_RECORD)
# 두 파일이 든 NC 표 — (파일, 절 머리). 열린 줄은 앞의 것, 닫힌 줄은 뒤의 것에 산다
_NC_TABLES = ((_LEDGER, "부적합 대장"), (_LEDGER_RECORD, "닫힌 부적합"))


def _ledger_text() -> str:
    """대장 두 파일을 이어 붙인 글 — 회차 절 · W 표처럼 **어느 파일에 있든** 세는 자리."""
    return "\n".join(path.read_text() for path in _LEDGER_FILES)


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
# 이 게이트가 대장 **전체**를 훑던 때(⑱)는 「로 시작한다」로 고르면 「아직 아무도 보지
# 않은 것」 표의 `⑰ 이 고친 자리(…)` 같은 행까지 세어, **회차별 W 표에서 줄을 지워도
# 게이트가 통과했다**(어긋내 확인했다). 지금은 W 표의 절만 훑으므로(NC-188) 그 표는
# 들어오지 않는다 — 「로 시작한다」로 바꿔도 오늘은 문다(감사 ㉖ NC-193). 그래도 이름뿐인
# 행만 세는 것은 그 절에 회차 기호로 시작하는 다른 줄이 서는 날을 위해서다.
_ROUND_LABEL = re.compile(r"[①-⑳㉑-㉟㊱-㊿](?:-b)?(?:\s+[가-힣]{1,3})?\Z")


# 회차별 W 표가 사는 절의 머리 — 머리 뒤의 수(「— 0 건」)는 바뀔 수 있어 앞머리로 찾는다
_ROUND_TABLE_HEAD = "### 기한이 지난 W"


def _round_table(text: str) -> str:
    """회차별 W 표의 절 — 그 머리부터 다음 제목 앞까지 (감사 ㉕ NC-188).

    대장 **전체**를 훑으면 다른 표(⑦ 번호 대조표의 `⑦` 행 따위)가 회차를 채워, W 표의
    줄을 지워도 초록이었다.
    """
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(_ROUND_TABLE_HEAD))
    end = next(
        (i for i in range(start + 1, len(lines)) if _ANY_HEADING.match(lines[i])), len(lines)
    )
    return "\n".join(lines[start:end])


def _rounds_in_the_round_table(text: str) -> set[str]:
    """회차별 W 표에 줄이 있는 회차들 — 첫 칸이 **회차 이름뿐인** 행만 센다."""
    found: set[str] = set()
    for _, row in _table_rows(_round_table(text)):
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

    **W 표의 절만 훑는다**(감사 ㉕ NC-188). 대장 전체를 훑었을 때는 ⑦ 번호 대조표의
    `⑦` 행이 기호 ⑦ 을 채워, W 표에서 `⑦-b` 행을 지워도 초록이었다(어긋내 확인했다).

    **이 게이트가 못 보는 부류**(W-6 ③): 줄은 있는데 **내용이 틀린** 것
    (⑦-b 행이 아홉을 여덟으로 적었던 자리 — NC-93 — 가 그 부류다), 꼬리로만 갈리는
    회차(`⑦` 과 `⑦-b` 는 같은 기호라 한 줄로 센다), 그리고 **절도 줄도 없이
    지나간** 회차 — 그것은 이 파일이 아니라 대장 자신이 모르는 회차다.
    """
    ledger = _ledger_text()
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
    off = [
        f"  {path.name}:{line.strip()}"
        for path in _LEDGER_FILES
        for line in _off_contract(path.read_text())
    ]
    assert off == [], "대장이 이 게이트가 가르는 모양을 벗어났다:\n" + "\n".join(off)

    sections = _round_sections(_ledger_text())
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
    """칸 — **이스케이프하지 않은** 구분자로만 가른다(NC-157 과 같다). 셀 안의 `\\|` 를 구분자로
    읽으면 뒤 칸이 밀려 상태 칸이 다른 칸이 된다(PR #38 Codex 리뷰)."""
    inner = row.strip().removeprefix("|")
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [cell.strip() for cell in _UNESCAPED_BAR.split(inner)]


def _nc_rows(path: Path, head: str) -> list[list[str]]:
    """한 NC 표의 줄마다 칸 — 첫 칸이 번호인 줄만."""
    return [
        cells
        for _, row in _table_rows(_section(path.read_text(), head))
        if (cells := _row_cells(row))[0].isdigit()
    ]


def _all_nc_rows() -> list[list[str]]:
    """대장 두 파일의 NC 줄 전부 — 열린 표와 닫힌 표(ADR 0010)."""
    return [cells for path, head in _NC_TABLES for cells in _nc_rows(path, head)]


def _closed_ncs() -> set[int]:
    return {int(cells[0]) for cells in _all_nc_rows() if cells[4].startswith("**닫힘")}


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
    지우지 말고 그 번호를 첫 칸에서 뺀다. **재감사가 돌았는데 드는 번호가 하나도 닫히지
    않은 줄**(전부 부분 닫힘이나 유지로 남은 줄)도 못 본다 — 번호의 상태로는 재감사가
    돌았는지 가를 수 없다(감사 ㉕ NC-187 (i)). 반대 방향 — **아무 줄도 기다리지 않는
    NC** — 는 아래 게이트가 문다.

    **담당이 여럿인 줄도 거짓 양성을 낸다**(감사 ㉔ — NC-185). 한 담당이 제 몫을 닫아도
    다른 담당은 아직 기다린다 — 대장의 ⑧ 셋 행과 ⑫ 행이 그랬다. 그 줄을 지우면 남은
    담당의 재감사가 표에서 사라지므로, **줄을 담당별로 나눈다**. 닫은 담당의 줄은 지운
    줄이 되고, 남은 담당의 줄은 제 몫의 번호만 든다.
    """
    closed = _closed_ncs()
    assert closed, "부적합 대장에서 닫힌 줄을 찾지 못했다 — 이 게이트가 아무것도 견주지 않는다"

    waiting = _section(_LEDGER.read_text(), "아직 아무도 보지 않은 것")
    rows = [_row_cells(row) for _, row in _table_rows(waiting)]
    live = [cells[0] for cells in rows[1:] if not cells[0].startswith("~~")]
    # **앵커는 파서가 읽었다는 것이다 — 기다리는 일이 남았다는 것이 아니다** (감사 ㉞).
    # 처음에는 「살아 있는 줄 가운데 NC 를 기다리는 것이 있다」를 걸었는데, ㉞ 가 마지막
    # 사슬을 닫자 **옳은 상태에서** 빨개졌다. 지운 줄까지 포함해 NC 를 드는 줄을 읽었는지를
    # 건다 — 파서가 깨지면 그것도 0 이 된다.
    assert any(_waiting_on(cells[0].strip("~")) for cells in rows[1:]), (
        "NC 를 드는 줄을 하나도 읽지 못했다 — 이 게이트가 아무것도 견주지 않는다"
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


# 재감사를 기다리는 상태 — 고쳤거나(재감사가 닫는다), 새로 났거나(저자 판정 뒤 재감사가 닫는다)
_AWAITING = ("**고침", "**열림")


def _awaiting_ncs() -> set[int]:
    return {int(cells[0]) for cells in _all_nc_rows() if cells[4].startswith(_AWAITING)}


def test_an_nc_waiting_for_a_reaudit_has_a_row_that_waits_for_it() -> None:
    """**재감사를 기다리는 NC 는 「아직 아무도 보지 않은 것」의 살아 있는 줄이 든다** (NC-187).

    위 게이트는 「살아 있는 줄이 **닫힌** NC 를 기다리는가」만 본다 — 반대 방향, **아무도
    기다리지 않는 NC** 는 초록이었다. 실제로 NC-157 이 그랬다. ⑮ 의 고침 중에 저자가
    낸 줄인데 ⑮ 행의 첫 칸(153 ~ 156)에 들지 않았고, 그 재감사는 호출자가 범위에 적어
    주어서야 돌았다(감사 ㉕). 번호의 집합끼리 견준다 — 위 게이트와 같은 형태다.

    **이 게이트가 못 보는 부류**(W-6 ③): 상태 칸이 「고침」 · 「열림」으로 시작하지 않는데
    재감사를 기다리는 줄(「부분 닫힘」은 잇는 NC 가 닫혀야 닫히므로 그 NC 가 대신 든다),
    그리고 줄이 번호를 들되 **담당이 틀린** 것 — 그 줄의 감사자 칸은 보지 않는다.
    """
    # **앵커는 NC 줄을 읽었다는 것이다** (감사 ㉞) — 기다리는 NC 가 0 인 것은 옳은 상태일 수
    # 있다(㉞ 가 마지막 사슬을 닫은 뒤가 그랬다). 파서가 깨지면 NC 줄 자체가 0 이 된다.
    assert _all_nc_rows(), "대장에서 NC 줄을 찾지 못했다 — 이 게이트가 아무것도 견주지 않는다"
    awaiting = _awaiting_ncs()

    waiting = _section(_LEDGER.read_text(), "아직 아무도 보지 않은 것")
    rows = [_row_cells(row) for _, row in _table_rows(waiting)]
    named: set[int] = set()
    for cells in rows[1:]:
        if not cells[0].startswith("~~"):
            named |= _waiting_on(cells[0])

    orphans = sorted(awaiting - named)
    assert orphans == [], (
        "재감사를 기다리는 NC 인데 「아직 아무도 보지 않은 것」의 어느 살아 있는 줄도 "
        "그것을 들지 않는다 — 그 회차의 재감사 행 첫 칸에 넣는다:\n"
        + "\n".join(f"  NC-{number}" for number in orphans)
    )


# 상태 칸의 어휘 — 대장 「닫는 규칙」이 정한 말. 굵게 연다. 여기 없는 말로 쓴 줄은 위 두
# 게이트가 기다리는지 · 닫혔는지를 가르지 못한다(감사 ㉗ NC-196)
# 굵게는 **닫혀야** 굵게다 — 여는 `**` 만 있으면 GFM 은 굵게 그리지 않는다(PR #38 Codex 리뷰)
_STATUS = re.compile(
    r"\*\*(?:닫힘|부분 닫힘|고침|등록|반박|중복|열림 — 저자 판정 대기|이슈로 옮김 — #\d+)"
    r"(?:[ (—][^*]*)?\*\*"
)


def test_every_nc_status_opens_with_a_word_the_ledger_defined() -> None:
    """**부적합 대장의 상태 칸은 정해진 말로 연다** (감사 ㉗ — NC-196).

    대장 「닫는 규칙」은 판정 전 상태를 「열림 — 저자 판정 대기」로 적고 「다른 말로 적지
    않는다」고 했는데 그것을 무는 것이 산문뿐이었다. 위의 두 게이트는 상태 칸의 **머리
    글자**(`**고침` · `**열림` · `**닫힘`)로 가르므로, 「판정 대기」처럼 적거나 굵게 하지
    않으면 재감사를 기다리는 줄이 아무 줄에도 없어도 초록이었다(어긋내 확인했다).

    **이 게이트가 못 보는 부류**(W-6 ③): 말은 맞는데 **상태가 틀린** 줄 — 재감사가 닫지
    않았는데 「닫힘」으로 적은 것은 문장을 읽어야 가른다. 그리고 부적합 대장 밖의 표.
    """
    rows = _all_nc_rows()
    assert rows, "부적합 대장에서 NC 줄을 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    strange = [
        f"  NC-{cells[0]} — {cells[4][:40]}" for cells in rows if not _STATUS.match(cells[4])
    ]
    assert strange == [], (
        "상태 칸이 대장 「닫는 규칙」이 정한 말(굵게)로 열리지 않는다 — 기다리는 표 게이트가 "
        "그 줄을 가르지 못한다:\n" + "\n".join(strange)
    )


# 대장의 일이 끝난 상태 — 닫혔거나, 심각도 낮음이라 이슈로 옮겼다(ADR 0011). 이 줄은
# `회차-기록.md` 에 산다. 이슈로 옮긴 줄은 닫힌 것이 아니다 — 기다리는 표 게이트의
# 「닫힌 NC」에는 들지 않는다
_SETTLED = ("**닫힘", "**이슈로 옮김")

# 「부적합 대장」이 드는 다음 번호 — 번호의 상한은 표가 아니라 이 줄에서 읽는다
_NEXT_NUMBER = re.compile(r"\*\*다음 번호는 NC-(\d+) 이다\.\*\*")

# 두 NC 표 어디에도 줄이 없는 번호 — 사유와 함께 든다. 여기 없는 빈 번호는 옮기다 잃은 줄이다
_NOT_IN_AN_NC_TABLE = {
    21: "남은 것이 감사자 자신이라 「사본 특화 대기」 W-7 로 옮겼다(부적합 대장의 옛 주석)",
    26: "같은 이유로 W-8",
    30: "같은 이유로 W-9",
}


def test_an_nc_row_lives_in_the_table_its_status_names() -> None:
    """**열린 줄은 `README.md` 에, 닫힌 줄은 `회차-기록.md` 에 산다** (ADR 0010).

    대장이 한 파일로 자라, 열린 줄을 보려면 닫힌 줄과 회차 절을 전부 읽어야 했다. 두 파일로
    나눈 뒤로는 줄이 닫힐 때 사람이 옮긴다 — 옮기지 않으면 `README.md` 가 다시 자라고, 열린
    줄을 닫힌 표에 두면 기다리는 표 게이트들은 그 줄을 여전히 세지만 다음 조각을 여는 사람은
    보지 못한다. 옮기다 줄을 잃거나 두 표에 함께 두는 것도 여기서 문다 — 번호는 두 표를
    가로질러 하나다.

    **번호의 상한은 표가 아니라 「다음 번호」 줄에서 읽는다**(PR #45 Codex 리뷰). 두 표의 가장
    큰 번호를 상한으로 삼으면 가장 큰 줄을 잃었을 때 상한이 함께 내려가 초록이었다(어긋내
    확인했다) — 그러면 다음 회차가 그 번호를 다시 준다.

    **이 게이트가 못 보는 부류**(W-6 ③): 옮기면서 **글자가 바뀐** 줄(옮기기 전의 글자와 견줄
    것이 저장소에 없다), 닫힌 표 안의 순서, 그리고 상태가 「닫힘」인데 재감사가 닫지 않은 줄 —
    그것은 위 게이트의 「못 보는 부류」와 같다.
    """
    open_rows = _nc_rows(*_NC_TABLES[0])
    closed_rows = _nc_rows(*_NC_TABLES[1])
    assert open_rows and closed_rows, "NC 표 하나가 비었다 — 이 게이트가 아무것도 가르지 않는다"

    misplaced = [
        f"  {_LEDGER.name} 의 NC-{cells[0]} 가 닫혔거나 이슈로 갔다 — 「닫힌 부적합」으로"
        for cells in open_rows
        if cells[4].startswith(_SETTLED)
    ] + [
        f"  {_LEDGER_RECORD.name} 의 NC-{cells[0]} 가 닫히지 않았다 — 「부적합 대장」에 둔다"
        for cells in closed_rows
        if not cells[4].startswith(_SETTLED)
    ]
    assert misplaced == [], "NC 줄이 상태와 다른 표에 있다:\n" + "\n".join(misplaced)

    found = _NEXT_NUMBER.findall(_section(_LEDGER.read_text(), "부적합 대장"))
    assert len(found) == 1, f"「부적합 대장」에 「다음 번호」 줄이 하나가 아니다: {found}"
    next_number = int(found[0])

    counted = Counter(int(cells[0]) for cells in open_rows + closed_rows)
    twice = sorted(number for number, seen in counted.items() if seen > 1)
    lost = sorted(set(range(1, next_number)) - set(counted) - set(_NOT_IN_AN_NC_TABLE))
    beyond = sorted(number for number in counted if number >= next_number)
    stale = sorted(set(counted) & set(_NOT_IN_AN_NC_TABLE))
    assert (twice, lost, beyond, stale) == ([], [], [], []), (
        "NC 번호가 두 표를 가로질러 하나씩이 아니다 — "
        f"두 번 있는 번호 {twice} · 어디에도 없는 번호 {lost} · "
        f"「다음 번호」(NC-{next_number}) 이상인 번호 {beyond} — 다음 번호 줄도 올린다 · "
        f"`_NOT_IN_AN_NC_TABLE` 에 들었는데 표에 있는 번호 {stale}"
    )


# 원 지적이 심각도를 낮음으로 적은 꼴 — 「심각도 낮음」 · 「심각도는 **낮음**」, 그리고
# 감사자 출력 양식의 「심각도: 낮음」(PR #65 Codex 리뷰 — 그 꼴을 그대로 옮긴 줄이 빠졌다).
# 「낮음이 아니다」 · 「낮음 아님」은 낮음이 아니다(같은 리뷰 — 부정형이 보통 이상을 잡았다)
_LOW = re.compile(r"심각도\s*(?:는|[:：])?\s*\**낮음(?!\**\s*[이가은는]?\s*아[니님])")


def _original_finding(cells: list[str]) -> str:
    """줄의 **원 지적** — 「무엇」 칸과, 끝 칸에서 뒤의 판정이 붙기 전까지(PR #65 Codex 리뷰).

    끝 칸은 원 지적 뒤에 재감사 · 고침 판정이 「 · **…**」로 덧붙는다. 원 지적은 「제안:」
    앞에서 끝나고, 제안이 없는 줄은 첫 덧붙임 앞에서 끝난다. 줄 전체를 보면 뒤의 판정이 잔여나
    다른 NC 를 「심각도 낮음」으로 든 것만으로 보통 이상의 부모 줄이 낮음으로 잡혔다(어긋내
    확인했다).
    """
    tail = cells[5]
    end = tail.find("제안:")
    if end == -1:
        end = tail.find(" · **")
    return cells[1] + " " + (tail if end == -1 else tail[:end])


# 낮음인데 NC 로 남는 열린 줄 — 부분 닫힘인 부모가 잔여로 기다린다(대장 「심각도」의 예외)
# 지금은 없다 — 163 · 220 이 들었다가 각각 ㉚ · ㉝ 이 닫아 뺐다(아래 게이트가 물었다)
_LOW_KEPT_AS_NC: dict[int, str] = {}


def test_a_low_nc_goes_to_an_issue() -> None:
    """**심각도 낮음은 NC 로 두지 않고 GitHub 이슈(`audit-low`)로 낸다** (ADR 0011).

    대장의 낮음 줄이 전체의 대부분이었고, 낮음도 재감사가 닫아야 해 회차가 그것을 닫는 데
    쓰였다. 저장소 소유자가 낮음은 이슈로 내고 고친 커밋이 닫기로 정했다(2026-10-01). 규칙을
    무는 것이 사람뿐이면 다음 회차에 낮음 줄이 다시 NC 로 등록된다 — 그래서 `README.md` 의 열린
    줄 가운데 원 지적이 「심각도 낮음」인 줄을 센다.

    **원 지적만 본다**(`_original_finding`) — 뒤에 덧붙은 판정이 다른 NC 를 낮음으로 들어도 그
    줄은 낮음이 아니다.

    **이 게이트가 못 보는 부류**(W-6 ③): 원 지적에 심각도를 **적지 않은** 줄(낼 때 적지 않은
    옛 줄이 그랬다), 「낮음」을 다른 꼴로 적은 줄, 원 지적 안에 「제안:」이나 「 · **」가 먼저
    나와 심각도 문장이 잘려 나간 줄, 그리고 이슈 쪽 — 이슈가 실제로 있는지 · 라벨이 붙었는지 ·
    열려 있는지는 저장소 밖이라 보지 않는다.
    """
    open_rows = _nc_rows(*_NC_TABLES[0])
    assert open_rows, "열린 NC 줄을 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    low = [
        f"  NC-{cells[0]} — {cells[1][:50]}"
        for cells in open_rows
        if int(cells[0]) not in _LOW_KEPT_AS_NC and _LOW.search(_original_finding(cells))
    ]
    assert low == [], (
        "심각도 낮음인 줄이 NC 로 열려 있다 — 이슈(`audit-low`)로 내고 상태를 "
        "「이슈로 옮김 — #n」으로 적어 「닫힌 부적합」으로 옮긴다:\n" + "\n".join(low)
    )

    numbers = {int(cells[0]) for cells in open_rows}
    stale = sorted(set(_LOW_KEPT_AS_NC) - numbers)
    assert stale == [], f"`_LOW_KEPT_AS_NC` 의 번호가 열린 줄이 아니다 — 목록에서 뺀다: {stale}"


def test_a_round_section_lives_in_the_record() -> None:
    """**회차 절은 `회차-기록.md` 에만 선다** (ADR 0010, PR #45 Codex 리뷰).

    회차 절을 세는 게이트들은 두 파일을 이어 읽으므로(`_ledger_text`), 새 회차 절을 옛 자리인
    `README.md` 끝에 두어도 초록이었다(어긋내 확인했다). 그러면 살아 있는 쪽이 다시 자라고,
    다음 감사자는 `회차-기록.md` 에서 지난 회차와 그 `### UNK-n` 을 찾지 못한다. 회차를
    **가리키는** 절(번호 대조)도 회차 기록이라 `## 감사 ` 로 여는 머리는 전부 본다.

    **이 게이트가 못 보는 부류**(W-6 ③): `## 감사 ` 로 열지 않는 회차 기록(`## PR 리뷰 —` 같은
    머리)과, 회차 절의 몸만 `README.md` 의 다른 절 아래에 붙인 것.
    """
    heads = [
        f"  {number}: {line}"
        for number, line, in_code in _ledger_lines(_LEDGER.read_text())
        if not in_code and line.startswith("## 감사 ")
    ]
    assert heads == [], (
        f"{_LEDGER.name} 에 회차 절이 있다 — {_LEDGER_RECORD.name} 끝으로 옮긴다:\n"
        + "\n".join(heads)
    )


# **게이트 파일** — 산문 · 경계 · 의존성을 무는 검사가 사는 자리(감사 ㉕ NC-189). 이 파일들의
# 검사는 어긋내 빨개지는 것을 본 기록이 `docs/audit/mutations.md` 의 표에 있어야 한다.
# 목록은 이름이다 — 게이트 파일이 새로 서면 여기 더한다(아래 「못 보는 부류」).
_GATE_FILES = ("tests/test_prose.py", "tests/test_boundary.py", "tests/test_dependencies.py")
_TEST_NAME = re.compile(r"test_[a-z0-9_]+")


# 기록 표의 머리 — 이 모양의 표만 「빨개진 검사」 칸을 든다
_RECORD_HEAD = ["NC", "무엇을 어긋냈나", "빨개진 검사"]


def _green_outside_record_tables() -> list[str]:
    """머리가 기록 표가 **아닌** 표에서 **어느 칸이든** `없다` 로 여는 칸 — 굵게 하든 않든 본다.

    기록 표의 머리를 한 낱말 바꾸면 그 표의 초록 줄이 초록 게이트 밖에 섰다(감사 ㉘ NC-205).
    처음에는 굵은 `<strong>없다` 만 봐서, 머리가 다른 표에 **굵게 하지 않은** 초록 줄을
    두면 어느 게이트에도 걸리지 않았다(감사 ㉙ NC-213, 어긋내 확인했다). 독스트링은 한때
    「셋째 칸」이라 적었는데 코드는 처음부터 모든 칸을 봤다(감사 ㉙ NC-217).
    """
    html = cmarkgfm.github_flavored_markdown_to_html(
        _mutation_bundles(), options=Options.CMARK_OPT_SOURCEPOS
    )
    found: list[str] = []
    for table in re.finditer(r'<table data-sourcepos="(\d+):[^"]*">(.*?)</table>', html, re.S):
        head, _, body = table.group(2).partition("</thead>")
        names = [
            re.sub(r"<[^>]+>", "", cell).strip()
            for cell in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)
        ]
        if names == _RECORD_HEAD:
            continue
        if re.search(r"<td[^>]*>\s*(?:<strong>)?없다", body):
            found.append(f"  mutations.md:{table.group(1)} — 머리 {names}")
    return found


def _mutation_record_rows() -> list[tuple[str, list[str], list[str]]]:
    """어긋냄 묶음의 **기록 표** 본문 줄 — (잰 커밋, 칸의 글자, 칸의 HTML), 문서 순서대로.

    표와 제목은 cmark-gfm 이 가른다(`_bundles_with_a_table` 과 같다). 머리가 기록 표인 표만
    든다 — 설명 · 실측 표의 줄은 기록이 아니다(PR #38 Codex 리뷰). 커밋은 그 표 바로 위의
    가장 가까운 제목에서 읽는다.
    """
    text = _mutation_bundles()
    html = cmarkgfm.github_flavored_markdown_to_html(text, options=Options.CMARK_OPT_SOURCEPOS)
    lines = re.split(r"\r\n|\r|\n", text)

    def plain(cell: str) -> str:
        return re.sub(r"<[^>]+>", "", cell).strip()

    headings = {
        int(found.group(1)): lines[int(found.group(1)) - 1]
        for found in re.finditer(r'<h[1-6] data-sourcepos="(\d+):', html)
    }
    rows: list[tuple[str, list[str], list[str]]] = []
    for table in re.finditer(r'<table data-sourcepos="(\d+):[^"]*">(.*?)</table>', html, re.S):
        above = [number for number in headings if number < int(table.group(1))]
        found = _COMMIT.search(headings[max(above)]) if above else None
        commit = found.group(0).strip("`") if found else ""
        head, _, body = table.group(2).partition("</thead>")
        if [
            plain(cell) for cell in re.findall(r"<th[^>]*>(.*?)</th>", head, re.S)
        ] != _RECORD_HEAD:
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [cell.strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            rows.append((commit, [plain(cell) for cell in cells], cells))
    return rows


def test_every_gate_has_a_record_of_turning_red() -> None:
    """**새 검사는 어긋내서 빨갛게 되는 것을 본다 — 기록은 `mutations.md`** (`CLAUDE.md`).

    그 규칙을 무는 것이 사람뿐이었고, 같은 모양이 거듭 났다. NC-156 이 「돌렸는데 기록의
    자리에 없다」를 없앤 바로 그 고침 회차에 NC-157 이 결과를 대장에만 적었고, 그 뒤 선
    게이트 셋은 기록이 아예 없었다(감사 ㉕ NC-189). 게이트 파일의 검사 이름이 전부 그
    파일의 **표 안에** 나와야 한다 — 산문에 이름만 든 것은 기록이 아니다.

    **이 게이트가 못 보는 부류**(W-6 ③): 기록이 있으나 **지금도 참인지** — 그 뒤 검사가
    바뀌어 더는 물지 않아도 옛 줄이 통과시킨다(묶음의 커밋이 그것을 되짚는 자리다). 셋째 칸을
    `**없다` 로 연 초록 줄의 이름은 **세지 않는다**(감사 ㉘ NC-203 — 초록을 기계로 가를 수 있게
    된 뒤다). 그 규칙 전의 옛 초록 줄(`_LEGACY_RESULT`)은 이름이 있으면 센다. 그리고
    `_GATE_FILES` 밖의 테스트 —
    게이트 파일이 새로 서도 이 목록에 들기 전에는 보지 않는다. 줄 머리의 `def test_` 만
    세므로 **들여쓴 메서드와 `async def` 검사**도 보지 않는다(오늘 0 건).

    **셋째 칸(「빨개진 검사」)의 이름만 센다**(감사 ㉗ NC-198). 처음에는 표의 모든 칸을
    셌는데, 그러면 「무엇을 어긋냈나」 칸이나 실측 표에 이름이 든 다른 줄이 기록을 대신
    채웠다 — 155 의 `chmod -x` 줄을 지워도 초록이었고(㉖ R4), 그 이름을 둘째 칸에 든
    189 줄이 그 틈을 만들었다(어긋내 확인했다). **기록 표만 센다** — 머리가 `NC` ·
    `무엇을 어긋냈나` · `빨개진 검사` 인 표다. 표는 파서가 가른다(PR #38 Codex 리뷰) — 셋째 칸을
    손으로 가르면 설명 · 실측 표의 셋째 칸도 「빨개진 검사」로 읽혔고, 인용 안의 표나 앞 파이프
    없는 표는 보이지 않았다.
    """
    recorded = {
        name
        for _, cells, html in _mutation_record_rows()
        if not html[2].startswith("<strong>없다")
        for name in _TEST_NAME.findall(cells[2])
    }
    gates = [
        (path, name)
        for path in _GATE_FILES
        for name in re.findall(r"^def (test_\w+)", (BACKEND_ROOT / path).read_text(), re.M)
    ]
    assert gates, "게이트 파일에서 검사를 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    unrecorded = [f"  {path}::{name}" for path, name in gates if name not in recorded]
    assert unrecorded == [], (
        "어긋내 빨개지는 것을 본 기록이 docs/audit/mutations.md 의 표에 없다:\n"
        + "\n".join(unrecorded)
    )


# 셋째 칸이 빨강도 초록도 아닌 **옛 줄** — 「통과한 줄은 `**없다` 로 연다」 앞의 기록이라 고치지
# 않는다(`mutations.md` 규칙 줄의 「이 규칙 전의 옛 줄 … 고치지 않는다」). 여기 없는 줄이 그
# 모양이면 빨갛다
_LEGACY_RESULT = {
    ("72392cf", "79"): "「통과했다」로 연 초록 — 규칙 앞",
    ("b2bb637", "154"): "검사가 아니라 명령의 범위를 잰 줄",
    ("fcb7570", "123"): "검사 이름 대신 제약이 문다고 적은 줄",
}


# 빨강 줄의 셋째 칸이 여는 모양 — 검사 이름의 코드이거나 「같은 검사」(감사 ㉘ NC-203)
_RED_OPENING = re.compile(r"<code>test_|같은 검사")

# 한 칸에 고치기 전 · 뒤를 함께 적은 옛 줄 가운데 **고치기 전의 글자로 연** 것 — 뒤의
# 빨강을 기록하므로 빨강으로 센다. 옛 줄을 어떻게 두는지는 `mutations.md` 규칙 줄 한 자리가
# 든다(감사 ㉙ NC-218). **셋째 칸이 여는 글자까지 든다** — (커밋, NC) 만으로는 같은 묶음 ·
# 같은 NC 의 다른 줄까지 봐주었다(PR #39 Codex 리뷰)
_BEFORE_AND_AFTER = {
    ("b2bb637", "153"): "고치기 전에는",
    ("b2bb637", "155"): "고치기 전에는",
    ("5472330", "164"): "처음에는 없었다",
    ("b701a19", "142"): "첫 판에서는",
    ("9c09a96", "109"): "처음에는 통과했다",
}


# 빨강 줄의 셋째 칸에 **고치기 전의 결과**가 함께 든 표시 — 「전 · 후는 두 줄로」
# (`mutations.md` 규칙 줄)를 어긴 모양이다. 검사 이름으로 열기만 하면 빨강으로 세던 때는
# 「`test_…` — 통과했다」인 순수한 초록 줄이 앞 초록을 닫고 기록 게이트의 기록을 채웠다
# (감사 ㉙ NC-214, 어긋내 확인했다). 이 파일에 이미 쓰인 전(前) 표현을 모두 든다 —
# 「처음에는」 · 「첫 판」은 `_BEFORE_AND_AFTER` 의 옛 줄이 쓴 말인데 처음에 빠졌다
# (PR #41 Codex 리뷰)
_A_PASS_INSIDE_RED = re.compile(r"통과했다|초록이었다|고치기 전|전에는|전까지|처음에는|첫 판")

# 한 칸에 고치기 전 · 뒤를 함께 적은 옛 줄 가운데 **검사 이름으로 연** 것 — 뒤의 빨강을
# 기록하므로 빨강으로 센다. 옛 줄을 어떻게 두는지는 `mutations.md` 규칙 줄 한 자리가
# 든다(감사 ㉙ NC-218). 규칙 앞의 줄이고, `e0159e2` 의 203 만 규칙 바로 뒤에 섰다(감사 ㉙
# NC-219 — 고치기 전 결과는 돌린 것이 아니다, 「감사 ㉙ 의 고침」 묶음이 바로잡는다).
# **셋째 칸이 여는 글자까지 든다** — (커밋, NC) 만으로는 같은 묶음 · 같은 NC 의 다른 줄까지
# 봐주었다(PR #41 Codex 리뷰 — `_BEFORE_AND_AFTER` 와 같은 까닭)
_RED_WITH_A_PASS = {
    ("fc940e8", "87"): "test_a_pass_is_actually_committed — 그 전에는",
    ("fc940e8", "90"): "test_the_same_request_twice_makes_two_lots · test_a_split_delivery_of",
    ("5f9922c", "132"): "같은 검사 — 앵커가 물었다. 그 전까지",
    ("4abd1b6", "186"): "test_a_mutation_bundle_says_which_commit_it_was_measured_on — 고치기",
    ("4abd1b6", "188"): "test_a_round_that_closed_leaves_a_line_in_the_round_table — 고치기 전",
    ("4abd1b6", "190"): "test_the_entrypoint_stops_at_the_first_failure — 고치기 전",
    ("0a92e57", "195"): "test_a_mutation_bundle_says_which_commit_it_was_measured_on — 고치기",
    ("0a92e57", "198"): "test_every_gate_has_a_record_of_turning_red — 고치기 전",
    ("bbfb6e8", "—"): "test_every_check_step_is_still_there_and_can_still_fail — ㉕ M6-d",
    ("e0159e2", "203"): "test_every_gate_has_a_record_of_turning_red — 초록 줄의 이름은",
}


def _green_and_later_red() -> tuple[list[tuple[str, str, int]], dict[str, int]]:
    """기록 표의 초록 줄 (커밋, NC, 순번) 과, NC 마다 **마지막** 빨강 줄의 순번.

    초록 줄은 셋째 칸을 굵은 `**없다` 로 연 줄이다(이 파일의 규칙). 초록과 빨강을 **같은 기록 표
    집합**에서 읽는다 — 줄 머리 파이프로 손으로 가르면 인용 안 · 앞 파이프 없는 기록 표의 초록
    줄이 빠지고, 설명 표의 수 칸이 빨강으로 읽혔다(PR #38 Codex 리뷰).

    빨강은 셋째 칸을 검사 이름(코드)이나 「같은 검사」로 **여는** 줄이다. 처음에는 검사 이름이
    칸 **어디에** 들어도 빨강으로 셌는데, 이 파일의 초록 줄은 검사 이름을 괄호로 들므로 `**` 만
    빠뜨린 초록 줄이 빨강으로 읽혀 색인 없이 지나고 앞 초록까지 닫았다(감사 ㉘ NC-203, 어긋내
    확인했다). **셋 다 아닌 줄은 실패다** — 그대로 빨강으로 치면 형식을 어긴 초록 줄이 앞
    초록 줄을 거짓으로 닫았다(PR #38 Codex 리뷰). 옛 줄은 `_LEGACY_RESULT` ·
    `_BEFORE_AND_AFTER` 에 이름으로 든다.

    **검사 이름으로 열어도 고치기 전의 결과(`_A_PASS_INSIDE_RED`)를 함께 적은 줄은 실패다** —
    여는 모양만 보던 때는 「`test_…` — 통과했다」인 초록 줄이 빨강으로 읽혀 앞 초록을
    닫았다(감사 ㉙ NC-214). 두 줄로 나눈다. 옛 줄은 `_RED_WITH_A_PASS` 에 이름으로 든다.
    """
    green: list[tuple[str, str, int]] = []
    last_red: dict[str, int] = {}
    strange: list[str] = []
    for order, (commit, cells, html) in enumerate(_mutation_record_rows()):
        if html[2].startswith("<strong>없다"):
            green.append((commit, cells[0], order))
        elif (
            _RED_OPENING.match(html[2])
            and _A_PASS_INSIDE_RED.search(cells[2])
            and not cells[2].startswith(_RED_WITH_A_PASS.get((commit, cells[0]), "\0"))
        ):
            strange.append(f"  묶음 `{commit}` · NC {cells[0]} — 고치기 전 결과가 함께 들었다")
        elif _RED_OPENING.match(html[2]) or cells[2].startswith(
            _BEFORE_AND_AFTER.get((commit, cells[0]), "\0")
        ):
            if cells[0].isdigit():
                last_red[cells[0]] = order
        elif (commit, cells[0]) not in _LEGACY_RESULT:
            strange.append(f"  묶음 `{commit}` · NC {cells[0]} — {cells[2][:40]}")
    assert strange == [], (
        "기록 표의 셋째 칸이 빨강(검사 이름 · 「같은 검사」)도 초록(`**없다`)도 아니거나, "
        "빨강 칸에 고치기 전 결과가 함께 들었다 — 두 줄로 나눈다:\n" + "\n".join(strange)
    )
    return green, last_red


def test_a_mutation_that_stayed_green_is_closed_later_or_listed() -> None:
    """**초록으로 남은 어긋냄은 뒤의 빨강으로 잇거나 「아직 초록인 어긋냄」에 든다** (㉕ OB-1).

    통과한 줄은 값이 크다 — 검사가 그 자리를 지키지 않는다는 뜻이다(이 파일의 규칙). 그런데
    **뒤에 게이트가 생겨 이제 무는 줄과 여전히 초록인 줄이 같은 모양으로 섞여** 알려진 사각을
    뽑을 자리가 없었다 — ⑪ ③ · ⑮ OB-1 · ㉕ OB-1 에 이어 ㉗ 에서 넷째가 났다. 저장소 소유자가
    자리와 검사를 함께 세우기로 정했다(2026-09-30).

    초록 줄마다 둘 중 하나다 — 같은 NC 의 빨강 줄이 **그 뒤에** 있거나(고쳐서 문다), 초록 절에
    그 묶음의 커밋과 NC 로 든다(닫는 조건과 지금이 함께 적힌다). 절의 줄은 닫혀도 지우지 않고
    「지금」 칸을 고친다 — 그 사각이 언제 어떻게 닫혔는지가 남는다.

    **이 게이트가 못 보는 부류**(W-6 ③): 셋째 칸을 `**없다` 로 열지 않은 옛 줄
    (`_LEGACY_RESULT` — 그 규칙 전의 기록이라 고치지 않는다), 뒤의 빨강 줄이 **다른 어긋냄**을
    문 것(NC 만 견준다 — 실제로 ㉗ 의 196 초록을 다른 어긋냄의 빨강이 닫았고, 그 줄은 색인에
    따로 든다, 감사 ㉘ NC-204), NC 가 `—` 인 초록 줄이 한 묶음에 둘 이상일 때 어느 것인지, 원시
    HTML `<table>` 로 쓴 표(파서가 표로 만들지 않는다), 그리고 절의 「지금」 칸이 참인지.

    **훑는 집합을 낱말이 정하지 않게 했다**(감사 ㉘ NC-205). 기록 표가 아닌 표의 칸이
    `없다` 로 열면 굵게 하든 않든 빨갛고(감사 ㉙ NC-213), 초록 절에서는 색인 표만 뺀다 — 그 절
    안에 둔 묶음도 훑는다.
    """
    green, last_red = _green_and_later_red()
    assert green, "초록 줄을 찾지 못했다 — 이 게이트가 아무것도 세지 않는다"

    misheaded = _green_outside_record_tables()
    assert misheaded == [], (
        "초록 줄(`**없다`)이 기록 표가 아닌 표에 있다 — 머리를 "
        f"{' · '.join(_RECORD_HEAD)} 로 쓴다:\n" + "\n".join(misheaded)
    )

    listed: set[tuple[str, str]] = set()
    for _, row in _table_rows(_section(_MUTATIONS.read_text(), _STILL_GREEN)):
        cells = _row_cells(row)
        if cells[0] != "기록":
            listed.update((found.strip("`"), cells[1]) for found in _COMMIT.findall(cells[0]))
    assert listed, "「아직 초록인 어긋냄」 절에 줄이 없다 — 이 게이트가 아무것도 견주지 않는다"

    loose = [
        f"  mutations.md 의 묶음 `{commit}` · NC {nc}"
        for commit, nc, order in green
        if not (nc in last_red and last_red[nc] > order) and (commit, nc) not in listed
    ]
    assert loose == [], (
        "초록으로 남은 어긋냄이 뒤의 빨강으로도 이어지지 않고 「아직 초록인 어긋냄」에도 "
        "없다 — 그 절에 커밋과 NC 로 적고 닫는 조건을 적는다:\n" + "\n".join(loose)
    )
