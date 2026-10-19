#!/usr/bin/env python3
"""설계 → 구현 관문 — 착공 PR 에 구현이 없고, 구현은 기준 가지에 머지된 설계 위에 서는지 본다. 모델도 네트워크도 안 쓴다.

  python3 scripts/verify-slice-gate.py                          # CI 는 이벤트, 로컬은 작업트리
  python3 scripts/verify-slice-gate.py --base <rev> --head <rev>  # 역사 재연

**왜 있나.** 절차 지도는 단계 3(구현)의 들어가는 조건을 「착공 PR 이 머지됐다」로 적었지만 무는 것이
없었다. 강호쟁패 #1 은 착공 문서와 검사 스크립트가 한 PR 이라 리뷰 12회차를 돌았다. claude-kit 은 한
세션이 PR 을 하나씩 열어 순서가 저절로 지켜졌을 뿐이다(조각 7 요구사항 「문제」).

**무엇을 보장하나.** `docs/slices/7-design-gate/design.md` ② 가 든다. 출력의 `[G1]` 같은 번호가 그
보장의 번호다 — 여기 따로 옮겨 적지 않는다. 받는 입력의 닫힌 목록은 같은 설계 ③.

**자리.** 실물은 `vibe-slice/skills/slice-docs/scripts/` 에 있고 플러그인 · 사본(`sync-slice.sh`)이 이 파일을 싣는다.
`scripts/verify-slice-gate.py` 는 그것을 가리키는 링크다(ADR 0018 의 3). 어느 레포에서든 그 작업트리에서 부른다.

이 검사를 망가뜨린 사본이 자체 시험에서 떨어지는지는 `bite-slice-gate.py` 가 본다 — 아래 줄 몇을 글자
그대로 찾아 바꾸므로, 그 줄을 고치면 변조본도 따라 고친다.

표준 라이브러리만 쓴다.
"""
import json
import os
import re
import subprocess
import sys

USAGE = "사용법: verify-slice-gate.py [--base <rev> --head <rev>]"
MASTER = "docs/master-plan.md"
SLICE_DOC = re.compile(r"^docs/slices/[^/]+/(requirements|design)\.md$")
ADR = re.compile(r"^docs/adr/[^/]+\.md$")
FOLDER = re.compile(r"^`(docs/slices/[^/`\s]+/)`")
HEADING = re.compile(r"^(#+) (.*)$")


class Unknown(Exception):
    """기준이나 머리를 정하지 못했다 — B2. 모르면 지나가지 않는다."""


def git(*args):
    # E2 git 이 내는 것(기준의 마스터플랜)은 UTF-8 로 읽는다 — 로케일 인코딩(cp949)으로 읽으면 한글이 깨지거나 예외로 끝난다.
    p = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def must(*args):
    rc, out = git(*args)
    if rc != 0:
        raise Unknown(f"git {' '.join(args)} 이 실패했다")
    return out


def sha(rev):
    rc, out = git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    return out.strip() if rc == 0 else None


def at_base(base, path):
    return git("cat-file", "-e", f"{base}:{path}")[0] == 0


# ── B1 · B2 기준과 머리 ──────────────────────────────────────────────

def from_event(path):
    """이벤트 JSON 의 기준 · 머리. `pull_request` 가 없으면 None — 이 길을 쓰지 않는다."""
    try:
        with open(path, encoding="utf-8") as f:
            ev = json.load(f)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Unknown(f"이벤트 JSON 을 읽지 못했다 — {type(e).__name__}")
    if not isinstance(ev, dict) or "pull_request" not in ev:
        return None
    try:
        pr = ev["pull_request"]
        base_sha, ref, head = pr["base"]["sha"], pr["base"]["ref"], pr["head"]["sha"]
        default = ev["repository"]["default_branch"]
    except (KeyError, TypeError):
        raise Unknown("이벤트 JSON 에 pull_request.base.sha · base.ref · head.sha · repository.default_branch 가 다 있지 않다")
    if not all(isinstance(v, str) and v for v in (base_sha, ref, head, default)):
        raise Unknown("이벤트 JSON 의 기준 · 머리 값이 글자가 아니다")
    # 쌓은 PR — 머지되지 않은 착공 가지 위의 구현 PR 을 기본 가지와 견줘 G1 로 떨어뜨린다(ADR 0016 의 5).
    base = base_sha if ref == default else f"origin/{default}"
    how = "이벤트" if ref == default else f"이벤트의 쌓은 PR — 기준 가지 {ref} 대신 {default}"
    return base, head, how


def pick(have):
    """로컬 기준 — `origin/main` 과 `main` 가운데 앞선 쪽. 갈라졌으면 `origin/main`."""
    if len(have) == 1:
        return next(iter(have))
    if git("merge-base", "--is-ancestor", have["origin/main"], have["main"])[0] == 0:
        return "main"
    return "origin/main"


def choose(argv):
    """(기준 rev, 머리 rev 또는 None=작업트리, 어디서) — B1."""
    if argv:
        return argv[0], argv[1], "인자"
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.isfile(path):
        got = from_event(path)
        if got:
            return got
    have = {r: s for r in ("origin/main", "main") if (s := sha(r))}
    if not have:
        raise Unknown("origin/main 도 main 도 없다")
    base = pick(have)
    return base, None, "로컬"


def changed(base, head):
    """merge-base(기준, 머리)에서 머리까지 바뀐 경로 — B3. 이름 바꿈은 옛 경로와 새 경로 둘 다."""
    mb = must("merge-base", base, head or "HEAD").strip()
    if head:
        out = must("diff", "--name-only", "--no-renames", mb, head)
    else:
        out = must("diff", "--name-only", "--no-renames", mb)
        out += must("ls-files", "--others", "--exclude-standard")
    return sorted({p for p in out.splitlines() if p})


# ── 기준 마스터플랜 — 문서 대조 검사(verify-docs.py 의 lines · section · table)와 같은 법(R3) ──

def lines(text):
    """코드 펜스와 줄 머리에서 연 주석을 뺀 줄."""
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


def section(ls, title):
    starts = [i for i, ln in enumerate(ls)
              if (m := HEADING.match(ln)) and len(m.group(1)) == 2 and m.group(2).rstrip() == title]
    if not starts:
        return []
    body = []
    for ln in ls[starts[0] + 1:]:
        m = HEADING.match(ln)
        if m and len(m.group(1)) <= 2:
            break
        body.append(ln)
    return body


def table(body):
    block, started = [], False
    for ln in body:
        if ln.startswith("|"):
            block.append(ln)
            started = True
        elif started:
            break
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in block[2:]]


def intent_of(ls):
    """「가리키는 문서」 의도 줄의 첫 경로 토막 — D1. 없으면 None."""
    for row in table(section(ls, "가리키는 문서")):
        if len(row) == 2 and row[0].startswith("의도") and (toks := re.findall(r"`([^`]+)`", row[1])):
            return toks[0]
    return None


def doing_of(ls):
    """「조각 나눔」의 `진행` 줄 — (조각, 폴더 또는 None). 표를 못 읽으면 None."""
    rows = [r for r in table(section(ls, "조각 나눔")) if len(r) == 6]
    if not rows:
        return None
    return [(name, m.group(1) if (m := FOLDER.match(folder)) else None)
            for _, name, _, _, state, folder in rows if state == "진행"]


# ── 판정 ────────────────────────────────────────────────────────────

def judge(base, paths):
    """G1 · G2 를 둘 다 본다. 실패 줄의 목록."""
    ls = lines(must("show", f"{base}:{MASTER}"))
    intent = intent_of(ls)

    def decision(p):
        return p in (intent, MASTER, "docs/procedure.md") or bool(ADR.match(p) or SLICE_DOC.match(p))

    outside = [p for p in paths if not decision(p)]
    founding = [p for p in paths if SLICE_DOC.match(p) and not at_base(base, p)]
    bad = []

    g1 = outside if founding else []
    if g1:
        bad.append(f"[G1] 착공 PR 에 결정 문서 밖의 파일이 있다 — 새 조각 문서 {', '.join(founding)} 와 함께: {', '.join(g1)}")

    if outside:
        doing = doing_of(ls)
        if doing is None:
            bad.append(f"[G2] 기준 마스터플랜의 「조각 나눔」 표를 읽지 못했다 — 결정 문서 밖: {', '.join(outside)}")
        else:
            ready = [n for n, folder in doing if folder and at_base(base, folder + "design.md")]
            if not ready:
                have = ", ".join(f"{n}({folder or '폴더 없음'})" for n, folder in doing) or "없다"
                bad.append(f"[G2] 기준에 설계가 머지된 `진행` 조각이 없다 — 기준의 `진행` 조각: {have}. "
                           f"결정 문서 밖: {', '.join(outside)}")
    return bad


def main(argv):
    if argv in (["-h"], ["--help"]):
        print(USAGE)
        return 0
    args = {}
    it = iter(argv)
    for a in it:
        if a not in ("--base", "--head") or a in args:
            print(USAGE, file=sys.stderr)
            return 2
        v = next(it, None)
        if not v:
            print(USAGE, file=sys.stderr)
            return 2
        args[a] = v
    if len(args) == 1:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        top = must("rev-parse", "--show-toplevel").strip()
        os.chdir(top)
        base, head, how = choose([args["--base"], args["--head"]] if args else [])
        base_sha = sha(base)
        if not base_sha:
            raise Unknown(f"기준 `{base}` 를 찾지 못했다")
        if head:
            head_sha = sha(head)
            if not head_sha:
                raise Unknown(f"머리 `{head}` 를 찾지 못했다")
            head = head_sha
        print(f"기준 {base_sha} ({base}) · 머리 {head or '작업트리'} · {how}")
        if not at_base(base_sha, MASTER):
            print("기준에 마스터플랜이 없다 — 보지 않는다")
            return 0
        paths = changed(base_sha, head)
    except Unknown as e:
        print(f"[B2] {e} — 모르면 지나가지 않는다")
        print("FAIL 설계 → 구현 관문")
        return 1

    if not paths:
        print("PASS 설계 → 구현 관문 — 바꾼 파일이 없다")
        return 0
    try:
        bad = judge(base_sha, paths)
    except Unknown as e:
        bad = [f"[B2] {e}"]
    for b in bad:
        print(b)
    if bad:
        print(f"FAIL 설계 → 구현 관문 — 바꾼 파일 {len(paths)}")
        return 1
    print(f"PASS 설계 → 구현 관문 — 바꾼 파일 {len(paths)}")
    return 0


if __name__ == "__main__":
    # E1 출력은 콘솔 인코딩과 상관없이 UTF-8 이다 — cp949 콘솔에서 `—` 를 찍다 예외로 끝나지 않게
    # (조각 9 설계 끝 「단계 5 에서 찾은 것」).
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
