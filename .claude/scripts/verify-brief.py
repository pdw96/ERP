#!/usr/bin/env python3
"""`/audit-brief` 가 쓴 브리핑을 **저장소의 git 출력과 직접** 견준다. 모델도 API 도 안 쓴다.

  python3 verify-brief.py <브리핑 파일> [--exclude <경로>]...

저장소 최상위에서 돌린다(하위 폴더에서 돌려도 최상위를 찾아 거기서 git 을 부른다).
`--exclude` 는 레포가 따로 둔 대장처럼 diff 에서 뺀 경로다 — 커맨드가 뺀 것과 같게 준다.

**왜 모양이 아니라 git 인가.** 예전 검사기는 모델이 쓴 마크다운의 모양을 정규식으로
봤다. 모양을 지키고 내용이 틀린 브리핑은 늘 더 만들 수 있어, 리뷰가 26차까지 가도
지적이 줄지 않았다(evals/README.md 「브리핑 검사기를 떼고, 러너를 고정했다」). 여기서는
브리핑이 **무엇을 담았다고 하는지**만 읽고, 담았어야 할 것은 git 에게 다시 묻는다.

보는 것:

- 머리 줄(「대상」 · 「기준」 · 「자름」)은 첫 절 앞에서만 읽고, 네 절은 한 번씩만 있는가
- 「대상」 SHA 가 지금 HEAD 인가 — 지난 회차의 브리핑이면 그 diff 는 이번 근거가 아니다
- 「기준」 SHA 가 커밋이고, 적힌 머지 베이스가 git 이 구한 것과 같은가
- git 이 말하는 변경 파일(커밋된 몫 · 작업트리 · 추적 안 된 파일)이 **하나도 빠짐없이**
  diff 절에 있거나 「담지 않은 것」에 경로가 백틱으로 통째로 적혀 있는가
- 담은 파일마다 +/- 줄 수 · 바이너리 블록 수 · 블록 수가 git 의 `--numstat` · `--raw` 와 같은가 —
  이름만 바꾼 블록처럼 줄이 없는 블록도 빠지면 드러난다. git 보다 많으면 늘 불일치다. 모자라면 잘린 것이므로
  「자름: 있음」이고 그 파일이 「담지 않은 것」에 적혀 있어야 한다
- git 에 없는 파일의 diff 가 들어 있지 않은가 — 지난 회차나 다른 기준의 것이 섞인 것이다

키 · 토큰을 앞 네 글자만 남기고 가려도 줄 수는 그대로라 대조는 견딘다. diff 는 커맨드처럼
`--no-ext-diff --no-textconv --submodule=short --ignore-submodules=none --no-color` 로 뽑았다고 본다.

보지 않는 것: 줄의 **내용**(가림과 부딪힌다), 커밋된 몫과 작업트리 몫을 제 소절에
나눠 담았는지(파일마다 합쳐서 센다), 「변경 파일」 · 「커밋」 절의 내용.

종료 코드: 0 통과, 1 불일치, 2 쓰는 법 · git 오류. 표준 라이브러리만 쓴다.
"""
import pathlib
import re
import subprocess
import sys

# 커맨드가 모든 `git diff` 에 붙이는 것과 같다 — 외부 diff · textconv · 서브모듈 요약 · 서브모듈
# 무시가 켜진 설정에서도 `diff --git` 블록과 날것의 줄 수가 나오게
PIN = ("--no-ext-diff", "--no-textconv", "--submodule=short", "--ignore-submodules=none", "--no-color")
DEFAULT_EXCLUDE = (".claude/audits", ".claude/briefs", ".claude/audit-brief.md")
SECTIONS = ("## 변경 파일", "## 커밋", "## diff", "## 이 브리핑이 담지 않은 것")


def git(top, *args, ok=(0,)):
    p = subprocess.run(["git", "-c", "color.ui=never", "-C", str(top), *args], capture_output=True)
    if p.returncode not in ok:
        raise RuntimeError(f"git {' '.join(args)} 실패: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


ESC = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def unquote(s):
    """git 이 따옴표로 감싼 경로(`"a/\\355\\225\\234.py"`)를 C 식으로 푼다. 안 감쌌으면 그대로.
    `\\ooo` 는 바이트, `\\t` 따위는 제 글자, 나머지 글자는 UTF-8 로 모아 한 번에 푼다 —
    `core.quotePath=false` 로 한글이 날것으로 남고 탭만 이스케이프된 이름도 풀린다."""
    if not (len(s) >= 2 and s[0] == s[-1] == '"'):
        return s
    body, out, i = s[1:-1], bytearray(), 0
    while i < len(body):
        if body[i] == "\\" and re.fullmatch(r"[0-7]{3}", body[i + 1:i + 4]):
            out.append(int(body[i + 1:i + 4], 8) & 0xFF)
            i += 4
        elif body[i] == "\\" and body[i + 1:i + 2] in ESC:
            out.append(ESC[body[i + 1]])
            i += 2
        else:
            out += body[i].encode("utf-8", "surrogateescape")
            i += 1
    return out.decode("utf-8", "surrogateescape")  # UTF-8 이 아닌 이름도 바이트 그대로 가른다


def unprefix(p, strip=True):
    """`a/` · `b/` 만이 아니라 `diff.mnemonicPrefix` 의 `c/ w/ i/ o/ 1/ 2/` 도 벗긴다. 한 겹만.
    `strip` 이 거짓이면(`diff.noprefix` — 머리 줄의 두 경로가 같다) 벗기지 않는다."""
    return p[2:] if strip and re.match(r"[abciwo12]/", p) else p


def header_pair(head):
    """머리 줄 `diff --git X Y` 를 (X, Y) 로. 이름 바꿈처럼 가를 수 없으면 None."""
    s = head[len("diff --git "):]
    m = re.fullmatch(r'("(?:[^"\\]|\\.)*") ("(?:[^"\\]|\\.)*")', s)
    if m:
        return unquote(m.group(1)), unquote(m.group(2))
    n = (len(s) - 1) // 2
    if len(s) % 2 == 1 and s[n] == " ":
        return s[:n], s[n + 1:]
    return None


def section(text, head):
    m = re.search(rf"^{re.escape(head)}[ \t]*(?:\n|\Z)([\s\S]*?)(?=^## |\Z)", text, re.M)  # 파일 끝의 머리도 빈 절로
    return m.group(1) if m else None


HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def parse_diff(body, order=()):
    """diff 절에서 파일마다 (+, -, 바이너리 블록 수, 블록 수) 를 모은다. 같은 경로가 두 번(커밋 몫 · 작업트리 몫)
    나오면 더한다. 헝크 안의 줄은 `@@ -a,b +c,d @@` 가 적은 수만큼만 먹는다 — 줄 모양으로
    짐작하지 않으므로 헝크 뒤에 붙은 글 · 헝크 안의 `--- a/` 모양 줄에 흔들리지 않는다.
    경로는 `+++ b/` · `rename to` · `--- a/` · 머리 줄 순서로 잡는다."""
    counts = {}
    body = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", body)  # color.ui=always 로 뽑은 diff
    marks = merge_marks(body, order)
    for blk in re.split(r"^(?=diff --(?:git|cc|combined) )", body, flags=re.M):
        if not blk.startswith("diff --"):
            continue
        lines = [ln for ln in blk.split("\n") if not ln.startswith("```")]
        head, path, minus_path, renamed = lines[0], None, None, None
        if head.startswith(("diff --cc ", "diff --combined ")):  # 풀지 않은 머지: merge_marks 가 센다
            continue
        pair = header_pair(head)
        strip = not (pair and pair[0] == pair[1])  # 두 경로가 같으면 접두가 없는 것이다
        add = rem = binary = old_left = new_left = 0
        for ln in lines[1:]:
            if old_left > 0 or new_left > 0:
                if ln.startswith("\\"):
                    continue
                if ln.startswith("+"):
                    add, new_left = add + 1, new_left - 1
                elif ln.startswith("-"):
                    rem, old_left = rem + 1, old_left - 1
                else:
                    old_left, new_left = old_left - 1, new_left - 1
                continue
            h = HUNK.match(ln)
            if h:
                old_left = int(h.group(1)) if h.group(1) is not None else 1
                new_left = int(h.group(2)) if h.group(2) is not None else 1
            elif ln.startswith("+++ "):
                p = unquote(ln[4:].rstrip("\t"))
                if p != "/dev/null":
                    path = unprefix(p, strip)
            elif ln.startswith("--- "):
                p = unquote(ln[4:].rstrip("\t"))
                if p != "/dev/null":
                    minus_path = unprefix(p, strip)
            elif ln.startswith(("rename to ", "copy to ")):  # 접두가 없는 줄이라 설정에 안 흔들린다
                renamed = unquote(ln.split(" to ", 1)[1])
            elif ln.startswith(("Binary files ", "GIT binary patch")):
                binary += 1
        path = renamed or path or minus_path
        if path is None and pair:  # 모드만 바뀐 파일 · 내용 없는 새 파일: 머리 줄에서 가른다
            x, y = unprefix(pair[0], strip), unprefix(pair[1], strip)
            if x == y:
                path = y
        if path is None:
            continue
        a, r, b, n = counts.get(path, (0, 0, 0, 0))
        counts[path] = (a + add, r + rem, b + binary, n + 1)
    return counts, marks


def mask_unmerged(text, unmerged, crlf=False):
    """블록 없이 나오는 `* Unmerged path <경로>` 줄의 경로를 자리표(`\\0` 과 번호)로 바꾼다.
    그 경로는 git 이 따옴표 없이 날것으로 적는다 — 풀면 `"q"` 와 `q` 가 겹치고, 줄바꿈이 든 이름은
    줄이 여럿에 걸쳐 둘째 줄이 `diff --git` · `## ` 모양일 수도 있고, 맨 `\\r` 로 끝나는 이름은 줄 끝이
    `\\r\\n` 이 된다. 그래서 절 · 블록을 가르거나 CRLF 를 풀기 **전에** `ls-files -u -z` 의 경로와
    긴 것부터 통째로 맞춰 한 줄로 만든다(짧은 이름이 긴 이름의 앞머리에 걸리지 않게). CRLF 로 저장한
    브리핑이면 경로 안의 줄바꿈도 `\\r\\n` 이다. 자리표 번호가 가리키는 경로 목록도 돌려준다."""
    order = sorted(unmerged, key=len, reverse=True)
    nl = "\r\n" if crlf else "\n"
    for i, p in enumerate(order):
        raw = p.replace("\n", nl)
        text = re.sub(r"^\* Unmerged path " + re.escape(raw) + rf"(?={re.escape(nl)}|\Z)",
                      f"* Unmerged path \0{i}", text, flags=re.M)
    return text, order


def merge_marks(text, order):
    """풀지 않은 머지의 표시를 경로 · 종류별로 센다 — `diff --cc`/`--combined` 블록과, 블록 없이
    나오는 `* Unmerged path` 줄(인덱스 몫은 늘, 수정/삭제 충돌은 작업트리 몫도 이것뿐). 그 줄은
    `mask_unmerged` 가 자리표로 바꿔 두었다. 어느 충돌 경로에도 안 맞은 줄은 첫 줄을 경로로 센다."""
    marks = {}

    def bump(key):
        marks[key] = marks.get(key, 0) + 1

    for m in re.finditer(r"^diff --(?:cc|combined) (.+)$", text, re.M):
        bump((unquote(m.group(1)), "cc"))
    for m in re.finditer(r"^\* Unmerged path (.*)$", text, re.M):
        i = re.fullmatch(r"\0(\d+)", m.group(1))
        bump((order[int(i.group(1))] if i else m.group(1), "unmerged"))
    return marks


def spans(text):
    """마크다운 코드 스팬의 내용들. 같은 길이의 백틱 줄로 열고 닫고, 양끝 빈칸 하나씩은 벗긴다
    (CommonMark). ``` ``foo`bar`` ``` 는 `foo` 가 아니라 `foo`bar` 한 덩어리다."""
    out = set()
    for m in re.finditer(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", text):
        c = m.group(2)
        if len(c) >= 2 and c[0] == c[-1] == " " and c.strip():
            c = c[1:-1]
        out.add(c)
    return out


def named_paths(omitted_spans, paths):
    """「담지 않은 것」에 코드 스팬 하나로 **통째로** 적힌 경로들. 빈칸 · 대시 · `@` 도 파일 이름에
    들 수 있어, 스팬 없이는 `app/routes.py backup` 같은 딴 경로와 못 가른다. 줄바꿈이 든 이름은
    스팬에 그대로 못 적으므로 git 이 적는 따옴표 모양(`"a\\nb"`)도 받는다. 다만 한 스팬이 그대로도
    풀어서도 바뀐 경로에 맞으면(`"foo"` 가 `"foo"` 와 `foo` 둘에) 어느 쪽인지 모르므로 치지 않는다."""
    out = set()
    for c in omitted_spans:
        hits = {c} | ({unquote(c)} if len(c) >= 2 and c[0] == c[-1] == '"' else set())
        hits &= paths
        if len(hits) == 1:
            out |= hits
    return out


def numstat(top, *args):
    """`git diff --numstat -z` → {경로: (+, -, 바이너리 몫 수)}. 바이너리는 (0, 0, 1). 이름 바꿈은 새 이름으로."""
    out = git(top, "diff", *PIN, "--numstat", "-z", *args).decode("utf-8", "surrogateescape")
    res, parts, i = {}, out.split("\0"), 0
    while i < len(parts):
        rec = parts[i]
        if not rec:
            i += 1
            continue
        a, d, path = rec.split("\t", 2)
        if path == "":  # 이름 바꿈: 다음 둘이 옛 이름 · 새 이름
            path = parts[i + 2]
            i += 3
        else:
            i += 1
        res[path] = (0, 0, 1) if a == "-" else (int(a), int(d), 0)  # 바이너리 블록은 헝크가 없어 0/0
    return res


def blocks(top, *args):
    """`git diff --raw -z` → ({경로: 블록 수}, 서브모듈 경로들). 이름 바꿈 · 복사는 새 이름으로. 종류가
    바뀐 파일(T)은 패치에서 지움 · 새로 만듦 두 블록이 된다. 이름만 바뀐 블록처럼 줄이 없는 몫도 여기서
    세므로, 같은 경로의 딴 몫이 줄 수를 채워도 블록 하나를 통째로 뺀 것이 드러난다. 어느 쪽이든
    gitlink(모드 160000)인 경로는 따로 모은다 — `numstat` 과 패치가 줄 수를 달리 센다."""
    parts = git(top, "diff", *PIN, "--raw", "-z", *args).decode("utf-8", "surrogateescape").split("\0")
    res, links, i = {}, set(), 0
    while i < len(parts):
        if not parts[i].startswith(":"):
            i += 1
            continue
        meta = parts[i].split()
        status = meta[-1]
        if status[0] in "RC":
            path, i = parts[i + 2], i + 3
        else:
            path, i = parts[i + 1], i + 2
        res[path] = res.get(path, 0) + (2 if status[0] == "T" else 1)
        if "160000" in (meta[0][1:], meta[1]):
            links.add(path)
    return res, links


def pathspec(excludes):
    # literal: `*` 같은 글자가 와일드카드로 풀려 모든 경로를 빼지 않게
    return ["--", ":/"] + [f":(top,literal,exclude){e}" for e in excludes]


def unmerged_paths(top, spec):
    """풀지 않은 머지의 경로들(`ls-files -u -z`)."""
    return {rec.split("\t", 1)[1] for rec in git(top, "ls-files", "-u", "-z", *spec).decode(
        "utf-8", "surrogateescape").split("\0") if "\t" in rec}


def expected(top, mb, spec, unmerged, order):
    want = {}

    def add(path, c):  # c 가 None 이면(안에 든 저장소 따위) 있는지만 — 딴 몫의 줄 수는 지킨다
        old = want.get(path)
        if old is None or c is None:
            want[path] = c if old is None else old
        else:
            want[path] = tuple(x + y for x, y in zip(old, c))

    # 풀지 않은 머지의 경로: 인덱스 몫은 `* Unmerged path` 한 줄, 작업트리 몫은 `diff --cc` 블록이라
    # 줄 수 · 블록 수를 git 과 같은 틀로 못 센다 — 두 몫은 세지 않고 git 이 내는 표시를 따로 요구한다
    # 커밋된 몫 · 인덱스 몫(HEAD→인덱스) · 작업트리 몫(인덱스→작업트리). `git diff HEAD` 한 번이면
    # 스테이지한 변경을 작업트리에서 되돌렸을 때 둘이 상쇄돼 다음 커밋에 들어갈 것이 안 보인다
    for rng in ((f"{mb}..HEAD",), ("--cached",), ()):
        ns, (bl, links) = numstat(top, *rng, *spec), blocks(top, *rng, *spec)
        if links:
            # 서브모듈은 패치로 센다 — 기록된 커밋은 그대로고 작업트리만 더러우면 `numstat` 은 0/0 인데
            # 패치에는 `-Subproject commit <sha>` · `+Subproject commit <sha>-dirty` 두 줄이 나온다
            # 경로를 좁히지 않는다 — 좁히면 이름 바꾼 gitlink 가 새 파일로 바뀌어 줄 수가 달라진다
            patch = git(top, "diff", *PIN, *rng, *spec)
            for path, c in parse_diff(patch.decode("utf-8", "surrogateescape"))[0].items():
                if path in links:
                    ns[path] = c[:3]
        for path in set(ns) | set(bl):
            if rng != (f"{mb}..HEAD",) and path in unmerged:
                continue
            add(path, ns.get(path, (0, 0, 0)) + (bl.get(path, 0),))
    for path in git(top, "ls-files", "-z", "--others", "--exclude-standard", *spec).decode(
            "utf-8", "surrogateescape").split("\0"):
        if not path:
            continue
        f = top / path
        if not (f.is_symlink() or f.is_file()):  # 안에 든 저장소 따위: 있는지만 본다
            add(path, None)
            continue
        # 커맨드와 같은 `--no-index` 로 git 에게 센다 — 링크(대상 한 줄) · `-diff` 속성
        # (바이너리) 을 git 과 다르게 셀 틈이 없다
        try:
            rec = git(top, "diff", *PIN, "--no-index", "--numstat", "-z", "--", "/dev/null", path,
                      ok=(0, 1)).decode("utf-8", "surrogateescape").split("\0")[0].split("\t")
        except RuntimeError:  # 못 읽는 파일 따위: 커맨드도 diff 를 못 뜬다 — 있는지만(「담지 않은 것」에)
            want[path] = None
            continue
        add(path, (0, 0, 1, 1) if rec[0] == "-" else (int(rec[0]), int(rec[1]), 0, 1))
    # 그 경로들에서 git 이 내는 표시를 커맨드와 같은 두 diff 로 센다 — 충돌 종류마다 모양이 다르다
    want_marks = {}
    if unmerged:
        out = b"".join(git(top, "diff", *PIN, *rng, *spec) for rng in (("--cached",), ()))
        out = mask_unmerged(out.decode("utf-8", "surrogateescape"), unmerged)[0]
        want_marks = {k: v for k, v in merge_marks(out, order).items() if k[0] in unmerged}
    return want, want_marks


def main(argv):
    sys.stdout.reconfigure(errors="backslashreplace")  # UTF-8 이 아닌 경로도 찍을 수 있게
    args, excludes = [], list(DEFAULT_EXCLUDE)
    it = iter(argv[1:])
    for a in it:
        if a == "--exclude":
            e = next(it, "").strip("/")
            if not e:  # 빈 제외는 `:(top,exclude)` 가 되어 모든 경로를 뺀다 — 대조가 꺼진다
                print("ERROR --exclude 뒤에 경로가 없다")
                return 2
            excludes.append(e)
        elif a.startswith("-"):
            print(__doc__)
            return 2
        else:
            args.append(a)
    if len(args) != 1:
        print(__doc__)
        return 2
    brief = pathlib.Path(args[0])
    try:
        # 줄 끝을 바꾸지 않고 읽는다 — 헝크 안의 맨 `\r` 이 줄로 바뀌면 헝크 수가 어긋난다
        text = brief.read_bytes().decode("utf-8", "surrogateescape")
        out = git(pathlib.Path.cwd(), "rev-parse", "--show-toplevel")
        # 저장소 폴더 이름도 UTF-8 이 아닐 수 있고, 빈칸으로 끝날 수도 있다 — git 의 줄 끝만 뗀다
        top = pathlib.Path((out[:-1] if out.endswith(b"\n") else out).decode("utf-8", "surrogateescape"))
        head = git(top, "rev-parse", "HEAD").decode().strip()
        spec = pathspec(excludes)
        unmerged = unmerged_paths(top, spec)
    except (OSError, RuntimeError) as e:
        print(f"ERROR {e}")
        return 2
    # 날것 경로의 `* Unmerged path` 줄을 절 · 블록을 가르고 CRLF 를 풀기 전에 한 줄로 만든다.
    # CRLF 로 저장했는지는 첫 줄(제목)로 가른다
    text, order = mask_unmerged(text, unmerged, crlf=text.split("\n", 1)[0].endswith("\r"))
    # CRLF 로 저장한 브리핑도 받는다. `\r\n` 만 `\n` 으로 — 맨 `\r` 은 지키고, 줄 수는 그대로다
    text = text.replace("\r\n", "\n")

    bad = []
    for s in SECTIONS:
        n = len(re.findall(rf"^{re.escape(s)}[ \t]*$", text, re.M))
        if n == 0:
            bad.append(f"절이 없다: {s}")
        elif n > 1:  # 첫 절만 읽히므로 뒤의 절은 대조 없이 감사자에게 간다
            bad.append(f"절이 {n}번 있다: {s} — 하나로 합쳐야 한다")
    head_md = re.split(r"^## ", text, maxsplit=1, flags=re.M)[0]  # 머리 줄은 첫 절 앞에서만 읽는다
    for key in ("대상", "기준", "자름"):  # 둘이면 첫 줄만 검사되고 뒤의 줄은 그대로 감사자에게 간다
        n = len(re.findall(rf"^- {key}:", head_md, re.M))
        if n > 1:
            bad.append(f"머리의 「{key}」 줄이 {n}개다 — 하나만 둔다")

    m = re.search(r"^- 대상:\s*`([0-9a-f]{4,64})`", head_md, re.M)
    if not m:
        bad.append("「대상」 줄에 HEAD 짧은 SHA 가 없다")
    elif not head.startswith(m.group(1)):
        bad.append(f"「대상」 {m.group(1)} 이 지금 HEAD {head[:12]} 가 아니다 — 지난 회차의 브리핑이다")

    mb = None
    base = re.search(r"^- 기준:.*?=\s*`([0-9a-f]{4,64})`", head_md, re.M)
    mbw = re.search(r"^- 기준:.*머지 베이스\s*`([0-9a-f]{4,64})`", head_md, re.M)
    if not base or not mbw:
        bad.append("「기준」 줄에 기준 SHA 와 머지 베이스가 없다")
    else:
        try:
            b = git(top, "rev-parse", "--verify", f"{base.group(1)}^{{commit}}").decode().strip()
            mb = git(top, "merge-base", b, "HEAD").decode().strip()
            if not mb.startswith(mbw.group(1)):
                bad.append(f"적힌 머지 베이스 {mbw.group(1)} 가 git 이 구한 {mb[:12]} 가 아니다")
                mb = None
        except RuntimeError as e:
            bad.append(f"기준 {base.group(1)} 을 풀지 못했다 — {e}")

    cut = re.search(r"^- 자름:\s*(없음|있음)", head_md, re.M)
    if not cut:
        bad.append("「자름」 줄이 없음 · 있음 으로 시작하지 않는다")

    body = section(text, "## diff")
    omitted = spans(section(text, "## 이 브리핑이 담지 않은 것") or "")
    if mb and body is not None:
        try:
            want, want_marks = expected(top, mb, spec, unmerged, order)
        except RuntimeError as e:
            print(f"ERROR {e}")
            return 2
        got, got_marks = parse_diff(body, order)
        # 충돌 경로는 커밋된 몫이 없으면(기준이 HEAD 등) want 에 없으므로 따로 더한다
        omitted = named_paths(omitted, set(want) | unmerged)
        for path in sorted(want):
            if path not in got:
                if path not in omitted:
                    bad.append(f"빠졌다: {path} — git 은 바뀌었다고 하는데 diff 에도 「담지 않은 것」에도 "
                               f"없다(「담지 않은 것」에는 경로를 백틱으로 통째로 적는다 — 줄바꿈이 든 이름은 "
                               f"git 이 적는 따옴표 모양으로)")
                continue
            if want[path] is not None and got[path] != want[path]:
                # 자름은 모자란 것만 풀어 준다 — git 보다 많은 줄 · 블록은 딴 데서 온 것이다
                over = any(g > w for g, w in zip(got[path], want[path]))
                if over or path not in omitted or not cut or cut.group(1) != "있음":
                    g, w = got[path], want[path]
                    bad.append(f"줄 수가 다르다: {path} — 브리핑 +{g[0]}/-{g[1]} 바이너리 {g[2]} 블록 {g[3]}, "
                               f"git +{w[0]}/-{w[1]} 바이너리 {w[2]} 블록 {w[3]}. 잘랐으면 「자름: 있음」과 "
                               f"「담지 않은 것」에 백틱으로 적어야 한다")
        for path in sorted(unmerged):
            w = {k: n for (p, k), n in want_marks.items() if p == path}
            g = {k: n for (p, k), n in got_marks.items() if p == path}
            over = any(n > w.get(k, 0) for k, n in g.items())  # 「담지 않은 것」은 모자란 것만 풀어 준다
            # 일부만 담았으면(표시 일부나 커밋된 몫) 잘린 것이다 — 보통 블록처럼 「자름: 있음」이어야
            partial = (g or path in got) and (not cut or cut.group(1) != "있음")
            if g != w and (over or path not in omitted or partial):
                bad.append(f"풀지 않은 머지가 git 과 다르다: {path} — 브리핑 {g or '없음'}, git {w or '없음'} "
                           f"(`diff --cc` 블록 · `* Unmerged path` 줄 — 일부만 담았으면 「자름: 있음」과 「담지 않은 것」에)")
        for path in sorted({p for p, _ in got_marks} - unmerged):
            bad.append(f"git 에 없는 머지 표시가 있다: {path} — 지금은 풀지 않은 머지가 아니다")
        for path in sorted(set(got) - set(want)):
            bad.append(f"git 에 없는 변경이 있다: {path} — 다른 기준 · 지난 회차의 diff 가 섞였다")

    if bad:
        print(f"FAIL {brief} — {len(bad)}건")
        for b in bad:
            print(f"  - {b}")
        return 1
    print(f"PASS {brief} — git 과 파일 · 줄 수가 맞다 (HEAD {head[:12]}, 머지 베이스 {mb[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
