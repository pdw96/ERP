#!/usr/bin/env python3
"""문서의 모양 — 절 제목 · 경로 · 조각 나눔 · 닫는 기록 — 을 대조한다. 모델도 네트워크도 git 도 안 쓴다.

  python3 scripts/verify-docs.py               # 이 저장소 — `scripts/` 의 링크로 부른다
  python3 scripts/verify-docs.py <루트>         # 다른 폴더 — 자체 시험이 베낀 트리로 쓴다
  python3 <이 파일> --repo <루트>                 # 다른 레포 — 원천은 이 파일 옆의 틀 넷

**자리.** 실물은 `vibe-slice/skills/slice-docs/scripts/` 에 있고 플러그인 · 사본(`sync-slice.sh`)이 이 파일을 싣는다.
`scripts/verify-docs.py` 는 그것을 가리키는 링크다(ADR 0018 의 3). 인자 없이 부르면 **부른 경로**의 두 단 위가 루트다 —
링크를 따라가지 않는다.

**왜 있나.** 절차 지도(`docs/procedure.md`)는 문서의 모양을 앵커볼트로 정했는데, 어겨도 떨어지는
검사가 없었다. 조각 2 착공 PR 안에서 문서 자리가 두 번 옮겨졌고, 가리키는 줄은 사람이 손으로
따라 고쳤다. 사람이 기억하는 검사는 건너뛴다.

**무엇을 보장하나.** `docs/slices/3-doc-check/design.md` ② 가 든다. 실패 줄의 `[O1]` 같은 번호가
그 보장의 번호다 — 여기 따로 옮겨 적지 않는다.

**모양의 원천은 `docs/procedure.md` 다.** 필수 제목은 그 파일의 「…의 칸」 표에서 읽는다. 여기에
있는 것은 그 표를 찾는 네 절 이름뿐이고, 그 자리는 앵커볼트다(`CLAUDE.md`, ADR 0010 의 8).

**다른 레포 모드(`--repo`)의 원천은 이 파일 옆의 틀 넷이다.** 지도는 다른 레포에 가지 않는다(ADR 0013 의 2). 틀의 `##`
제목은 claude-kit 에서 T2 가 「…의 칸」 표와 글자 그대로 같게 무니 같은 원천이다. 모드는 인자로만 고른다 —
`docs/slices/9-repo-doc-check/design.md` ② A(ADR 0018 의 2 · 5).

표준 라이브러리만 쓴다.
"""
import os
import pathlib
import re
import sys

# 「…의 칸」 절 이름 → 그 모양을 따르는 틀. 절 이름은 앵커볼트다.
KINDS = [
    ("의도 문서의 칸", "intent.md"),
    ("마스터플랜의 칸", "master-plan.md"),
    ("요구사항 문서의 칸", "requirements.md"),
    ("설계 문서의 칸", "design.md"),
]
# 틀이 사는 곳 — `vibe-slice` 플러그인의 스킬 폴더(ADR 0013 의 6). 다른 레포는 그 스킬로 틀을 받는다.
TEMPLATES = "vibe-slice/skills/slice-docs/templates"
STATES = ("예정", "진행", "닫힘")
CLOSING = re.compile(r"^닫으며 \(\d{4}-\d{2}-\d{2}\)$")
FOLDER = re.compile(r"^`(docs/slices/\d+-[^/`\s]+/)`$")
# 틀의 「가리키는 문서」가 박아 둔 조각 폴더의 자리 — 첫 조각 전에는 없다(설계 ② A7).
SLICES = "docs/slices/"
NONE_MARK = re.compile(r"^`?없음 — ")
HEADING = re.compile(r"^(#+) (.*)$")


class Report:
    def __init__(self, root):
        self.root = root
        self.bad = []

    def fail(self, path, gid, msg):
        rel = path.relative_to(self.root).as_posix() if isinstance(path, pathlib.Path) else path
        self.bad.append(f"{rel}: [{gid}] {msg}")

    def source(self, path, msg):
        """다른 레포 모드의 원천(틀)이 서지 않는다 — 틀은 루트 밖이라 경로를 그대로 찍는다(설계 ② A2)."""
        self.bad.append(f"[A2] {path.as_posix()}: {msg}")


# 읽지 못한 파일 — `lines()` 가 모으고 `main()` 이 [R1] 로 찍는다. 예외로 끝내지 않으려고 빈 줄로 돌려준다.
UNREADABLE = {}


def lines(path):
    """코드 펜스와 줄 머리에서 연 주석을 뺀 줄. 읽지 못하면 빈 목록 — 까닭은 UNREADABLE 에."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        UNREADABLE.setdefault(path, f"{type(e).__name__}: {e}")
        return []
    out, fence, comment = [], False, False
    for ln in text.splitlines():
        if comment:
            if "-->" in ln:
                comment = False
            continue
        if ln.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if ln.startswith("<!--"):
            comment = "-->" not in ln
            continue
        out.append(ln)
    return out


def headings(ls, depth=2):
    found = []
    for ln in ls:
        m = HEADING.match(ln)
        if m and len(m.group(1)) == depth:
            found.append(m.group(2).rstrip())
    return found


def section(ls, depth, title):
    """깊이 `depth` 의 제목 `title` 아래 줄들. 같은 제목이 몇 번 나왔는지도 돌려준다."""
    starts = [i for i, ln in enumerate(ls)
              if (m := HEADING.match(ln)) and len(m.group(1)) == depth and m.group(2).rstrip() == title]
    if not starts:
        return None, 0
    body = []
    for ln in ls[starts[0] + 1:]:
        m = HEADING.match(ln)
        if m and len(m.group(1)) <= depth:
            break
        body.append(ln)
    return body, len(starts)


def table(body):
    """절 안에서 처음 나오는 표의 칸 줄 — 머리와 가름줄은 뺀다."""
    block, started = [], False
    for ln in body:
        if ln.startswith("|"):
            block.append(ln)
            started = True
        elif started:
            break
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block[2:]]


def in_order(have, need):
    """`need` 가 `have` 안에 그 순서로 다 있나. 없는 것과 순서가 어긋난 것을 가른다."""
    missing = [t for t in need if t not in have]
    if missing:
        return f"필수 제목이 없다 — {', '.join(missing)}"
    it = iter(have)
    if not all(t in it for t in need):
        return f"필수 제목의 순서가 다르다 — {' → '.join(need)}"
    return None


def real(p):
    """링크를 따라간 실제 위치. 링크가 고리면 None — 판에 따라 예외가 나므로 여기서 받는다."""
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return None


def inside(root, tok):
    """경로 토막이 루트 안의 있는 자리인가. 아니면 까닭을 돌려준다."""
    if tok.startswith("/") or ".." in pathlib.PurePosixPath(tok).parts:
        return None, "저장소 밖을 가리킨다"
    p = root / tok
    where = real(p)
    if where is None:
        return None, "링크가 고리다"
    if not p.exists():
        return None, "없다"
    if not where.is_relative_to(root):
        return None, "링크가 저장소 밖을 가리킨다"
    if tok.endswith("/") and not p.is_dir():
        return None, "폴더가 아니다"
    return p, None


def readings(cell, names):
    """의존 칸을 조각 이름의 ` · ` 이음으로 읽는 길 — 셋째부터는 세지 않는다.

    되부름 없이 칸의 뒤에서부터 센다. 칸에 이름이 수천 개 이어져도 깊이 한도에 걸리지 않는다(R1).
    `ways[i]` 는 `cell[i:]` 를 읽는 길의 수(2 에서 멈춘다), `pick[i]` 는 그 가운데 하나의 첫 이름이다.
    """
    end = len(cell)
    ways, pick = [0] * (end + 1), [None] * (end + 1)
    for i in range(end - 1, -1, -1):
        for n in names:
            if not cell.startswith(n, i):
                continue
            j = i + len(n)
            if j == end:
                w = 1
            elif cell.startswith(" · ", j):
                w = ways[j + 3]
            else:
                w = 0
            if w and pick[i] is None:
                pick[i] = n
            ways[i] = min(2, ways[i] + w)
    if not ways[0]:
        return []
    one, i = [], 0
    while i < end:
        one.append(pick[i])
        i += len(pick[i]) + 3
    return [one] * ways[0]


def check_schema(r, root):
    proc = root / "docs" / "procedure.md"
    if not proc.is_file():
        r.fail("docs/procedure.md", "O3", "없다 — 문서의 모양을 읽을 곳이 없다")
        return {}
    ls = lines(proc)
    schema = {}
    for name, _ in KINDS:
        body, n = section(ls, 3, name)
        if n != 1:
            r.fail(proc, "O1", f"`### {name}` 이 {n} 번 있다 — 꼭 한 번이어야 한다")
            continue
        need = [m.group(1) for row in table(body) if (m := re.match(r"^`## (.+)`$", row[0]))]
        if not need:
            r.fail(proc, "O2", f"「{name}」 표에 필수 제목 줄이 없다")
            continue
        schema[name] = need
    return schema


def side_templates():
    """다른 레포 모드의 원천이 사는 곳 — 이 파일의 실제 자리(링크를 따라간)의 `../templates/`(설계 ② A1)."""
    return pathlib.Path(__file__).resolve().parent.parent / "templates"


def check_sources(r, tpl):
    """다른 레포 모드 — 필수 제목은 틀마다 그 `##` 제목 전부, 틀의 순서대로(설계 ② A1 · A2)."""
    schema = {}
    for name, fname in KINDS:
        p = tpl / fname
        if not p.is_file():
            r.source(p, f"틀이 없다 — 「{name}」의 원천을 읽을 곳이 없다")
            continue
        found = headings(lines(p))
        if p in UNREADABLE:
            r.source(p, f"읽지 못했다 — UTF-8 틀이어야 한다({UNREADABLE.pop(p)})")
            continue
        if not found:
            r.source(p, f"`##` 제목이 하나도 없다 — 「{name}」의 원천이 비었다")
            continue
        schema[name] = found
    return schema


def check_templates(r, root, schema):
    for name, fname in KINDS:
        p = root / TEMPLATES / fname
        if not p.is_file():
            r.fail(f"{TEMPLATES}/{fname}", "T1", "틀이 없다")
            continue
        if name in schema and headings(lines(p)) != schema[name]:
            r.fail(p, "T2", f"`##` 제목이 「{name}」 표와 다르다 — {' → '.join(schema[name])}")


def check_master(r, root, schema, repo):
    mp = root / "docs" / "master-plan.md"
    if not mp.is_file():
        r.fail("docs/master-plan.md", "O3", "없다 — 마스터플랜이 없다")
        return None
    ls = lines(mp)
    body, _ = section(ls, 2, "조각 나눔")
    rows = table(body or [])
    # A7 다른 레포 모드에서 `진행` · `닫힘` 줄이 하나도 없으면 아직 없는 `docs/slices/` 를 받는다 — 빈 폴더는 커밋되지 않는다.
    before_first = repo and not any(len(row) == 6 and row[4] in ("진행", "닫힘") for row in rows)
    need = schema.get("마스터플랜의 칸")
    if need and (why := in_order(headings(ls), need)):
        r.fail(mp, "M1", why)

    body, _ = section(ls, 2, "가리키는 문서")
    intents = []
    for row in table(body or []):
        if len(row) != 2:
            r.fail(mp, "M2", f"「가리키는 문서」 줄이 두 칸이 아니다 — {' | '.join(row)}")
            continue
        what, where = row
        is_intent = what.startswith("의도")
        if is_intent:
            intents.append(where)
        if NONE_MARK.match(where):
            if is_intent:
                r.fail(mp, "I2", "의도 줄은 `없음 — ` 을 받지 않는다")
            continue
        toks = re.findall(r"`([^`]+)`", where)
        if not toks:
            r.fail(mp, "I2" if is_intent else "M2", f"「{what}」 줄에 경로도 `없음 — <이유>` 도 없다")
            continue
        for tok in toks:
            if tok == SLICES and before_first and not os.path.lexists(root / tok):
                continue
            _, why = inside(root, tok)
            if why:
                r.fail(mp, "M2", f"「{what}」 줄의 `{tok}` 가 {why}")
        if is_intent:
            p, why = inside(root, toks[0])
            if why or not p.is_file():
                r.fail(mp, "I2", f"의도 줄의 `{toks[0]}` 가 저장소 안의 파일이 아니다 — {why or '폴더다'}")
            elif p.name == "INTENT.md" and (need := schema.get("의도 문서의 칸")):
                if why := in_order(headings(lines(p)), need):
                    r.fail(p, "I3", why)
    if len(intents) != 1:
        r.fail(mp, "I1", f"「가리키는 문서」에 의도 줄이 {len(intents)} 개다 — 꼭 하나여야 한다")
    return mp, rows


def check_slices(r, root, schema, mp, rows):
    good = []
    for row in rows:
        if len(row) != 6:
            r.fail(mp, "S1", f"조각 나눔 줄이 여섯 칸이 아니다({len(row)}) — {' | '.join(row)}")
        else:
            good.append(row)

    names = [row[1] for row in good]
    seen = set()
    for order, name, _, _, state, _ in good:
        if not re.fullmatch(r"\d+|—", order):
            r.fail(mp, "S2", f"「{name}」의 순서 `{order}` 가 숫자도 `—` 도 아니다")
        if not name or name == "—":
            r.fail(mp, "S3", f"조각 이름 `{name}` 은 쓸 수 없다")
        elif name in seen:
            r.fail(mp, "S3", f"조각 이름 「{name}」이 겹친다")
        seen.add(name)
        if state not in STATES:
            r.fail(mp, "S4", f"「{name}」의 상태 `{state}` 가 {' · '.join(STATES)} 가운데 하나가 아니다")
    status = {row[1]: row[4] for row in good}
    usable = [n for n in dict.fromkeys(names) if n and n != "—"]

    deps = {}
    for _, name, _, cell, state, _ in good:
        if cell == "—":
            deps[name] = []
            continue
        ways = readings(cell, usable)
        if len(ways) != 1:
            why = "조각 이름으로 읽히지 않는다" if not ways else "조각 이름으로 읽는 길이 둘 이상이다"
            r.fail(mp, "S5", f"「{name}」의 의존 `{cell}` 가 {why}")
            continue
        deps[name] = ways[0]
        if state in ("진행", "닫힘"):
            for d in ways[0]:
                if d == name:
                    r.fail(mp, "S6", f"「{name}」이 자기 자신을 의존한다")
                elif status.get(d) != "닫힘":
                    r.fail(mp, "S6", f"{state} 조각 「{name}」의 의존 「{d}」가 `닫힘` 이 아니다")

    # 고리 찾기 — 되부름 없이 쌓개로 걷는다. 의존 사슬이 길어도 깊이 한도에 걸리지 않는다(R1).
    state = {}
    for start in deps:
        if state.get(start):
            continue
        state[start] = 1
        stack = [(start, iter(deps[start]))]
        while stack:
            n, todo = stack[-1]
            d = next(todo, None)
            if d is None:
                state[n] = 2
                stack.pop()
            elif state.get(d) == 1:
                path = [x for x, _ in stack]
                cyc = path[path.index(d):] + [d]
                r.fail(mp, "S10", f"의존에 고리가 있다 — {' → '.join(cyc)}")
            elif d in deps and not state.get(d):
                state[d] = 1
                stack.append((d, iter(deps[d])))

    claimed, owner = set(), {}
    for _, name, _, _, state, cell in good:
        m = FOLDER.match(cell)
        if not m and not cell.startswith("—"):
            r.fail(mp, "S7", f"「{name}」의 폴더 칸 `{cell}` 가 `docs/slices/<숫자>-<이름>/` 하나도 `—` 도 아니다")
        folder = m.group(1) if m else None
        if folder:
            claimed.add(folder)
            # 링크로 다른 이름을 붙여도 같은 폴더다 — 따라간 실제 위치로 견준다.
            key = real(root / folder) or folder
            if key in owner:
                r.fail(mp, "S9", f"「{owner[key]}」와 「{name}」이 같은 폴더를 가리킨다 — `{folder}`")
            owner.setdefault(key, name)
        if state == "예정":
            if not cell.startswith("—"):
                r.fail(mp, "S8", f"예정 조각 「{name}」에 폴더가 있다 — `—` 여야 한다")
            continue
        if state not in ("진행", "닫힘"):
            continue
        if not folder:
            r.fail(mp, "S8", f"{state} 조각 「{name}」에 폴더 경로가 없다")
            continue
        p, why = inside(root, folder)
        if why:
            r.fail(mp, "S8", f"{state} 조각 「{name}」의 폴더 `{folder}` 가 {why}")
            continue
        req, des = p / "requirements.md", p / "design.md"
        if state == "진행":
            for f, kind in ((req, "요구사항 문서의 칸"), (des, "설계 문서의 칸")):
                if not f.is_file():
                    r.fail(f, "F2", f"진행 조각 「{name}」에 이 파일이 없다")
                    continue
                hs = headings(lines(f))
                if kind in schema and (why := in_order(hs, schema[kind])):
                    r.fail(f, "F3", why)
                if f is req and any(h.startswith("닫으며 (") for h in hs):
                    r.fail(f, "F4", f"진행 조각 「{name}」에 「닫으며」가 있다 — 닫았다면 상태를 `닫힘` 으로")
        else:
            if not req.is_file():
                r.fail(req, "F5", f"닫힌 조각 「{name}」에 요구사항이 없다")
            elif not any(CLOSING.match(h) for h in headings(lines(req))):
                r.fail(req, "F5", f"닫힌 조각 「{name}」에 `## 닫으며 (<YYYY-MM-DD>)` 가 없다")

    slices = root / "docs" / "slices"
    if slices.is_dir():
        for d in sorted(x for x in slices.iterdir() if x.is_dir()):
            if f"docs/slices/{d.name}/" not in claimed:
                r.fail(d, "F1", "조각 나눔의 어느 줄도 이 폴더를 가리키지 않는다")


def main(argv):
    repo = argv[:1] == ["--repo"]
    args = argv[1:] if repo else argv
    if len(args) > 1 or (repo and not args) or any(a.startswith("-") for a in args):
        print("사용법: python3 verify-docs.py [<루트> | --repo <루트>]", file=sys.stderr)
        return 2
    # W3 부른 경로의 두 단 위 — 링크를 따라가지 않는다. `scripts/` 의 링크로 부르면 이 저장소다.
    root = pathlib.Path(args[0]) if args else pathlib.Path(os.path.abspath(__file__)).parent.parent
    if not root.is_dir():
        print(f"루트 `{root}` 가 폴더가 아니다", file=sys.stderr)
        return 2
    root = root.resolve()
    r = Report(root)
    tpl = side_templates() if repo else None
    if tpl:
        # A3 다른 레포 모드는 지도와 루트의 틀을 보지 않는다 — 루트에 `docs/procedure.md` 가 있어도.
        schema = check_sources(r, tpl)
    else:
        schema = check_schema(r, root)
        check_templates(r, root, schema)
    got = check_master(r, root, schema, repo)
    if got:
        check_slices(r, root, schema, *got)
    for p, why in UNREADABLE.items():
        r.fail(p, "R1", f"읽지 못했다 — UTF-8 문서여야 한다({why})")

    if r.bad:
        print("FAIL")
        for b in r.bad:
            print(f"  - {b}")
        return 1
    if tpl:
        print(f"PASS 문서의 모양(다른 레포 — 원천 {tpl.as_posix()}) — 의도 · 마스터플랜 · 조각 나눔 · 조각 폴더")
    else:
        print("PASS 문서의 모양 — 원천 · 틀 · 의도 · 마스터플랜 · 조각 나눔 · 조각 폴더")
    return 0


if __name__ == "__main__":
    # E1 출력은 콘솔 인코딩과 상관없이 UTF-8 이다 — cp949 콘솔에서 `—` 를 찍다 예외로 끝나지 않게
    # (조각 9 설계 끝 「단계 5 에서 찾은 것」).
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
