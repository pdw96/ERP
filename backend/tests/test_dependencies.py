"""의존성은 **잠금 파일**에서 해시까지 맞춰 설치한다 — 감사 ⑳ 이 넘긴 「의존성 무결성」.

`requirements.in` · `requirements-dev.in` 은 **사람이 고치는 입력**이다. 무엇을
왜 쓰는지 적는 자리이고, 하위 의존성까지 고정하지는 않는다. 설치는 잠금
`requirements.txt` · `requirements-dev.txt` 에서 `--require-hashes` 로 한다 —
하위 의존성까지 버전과 해시가 박혀 있어 **같은 이름 · 같은 버전으로 다른 파일이
오면 설치가 멈춘다.**

입력과 잠금은 **두 벌**이다. 합칠 수 없으므로(입력에 해시를 적으면 사람이 고칠
수 없다) 견주는 검사가 그 자리를 대신한다 — 「목록을 두 벌 두지 않는다. 두 벌이면
반드시 갈린다」. 잠금을 매주 갱신하는 Dependabot 의 PR 도 이 검사를 탄다.

**이 파일이 못 보는 부류**(W-6 ③):

- **처음부터 엉뚱한 패키지를 고른 것.** 해시는 「처음 받은 그 파일」을 지킬 뿐이라
  이름을 잘못 적은 패키지(타이포스쿼팅)도 충실히 잠근다. 의존성을 더하는 날
  사람이 본다.
- **잠금이 리눅스 · 파이썬 3.12 에서 풀렸다는 것.** CI 와 이미지는 그 환경이다.
  다른 플랫폼에서만 붙는 의존성은 잠금에 없어 그 자리에서 설치가 멈춘다 —
  조용히 통과하지는 않는다.
- **잠금의 하위 의존성이 입력에서 실제로 나오는가.** 풀이를 다시 하지 않으므로
  「입력이 직접 부른다」고 적힌 줄과, 입력이 고른 **extra** 가 부르는 것만 견준다.
  extra 는 설치된 메타데이터의 마커에서 `extra == "…"` 를 글자로 찾는다 — 마커를
  풀어 계산하지 않는다.
"""

import re
from importlib.metadata import metadata, requires
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# 입력 → 잠금. 개발 입력은 `-r requirements.in` 으로 런타임 입력을 품고,
# `-c requirements.txt` 로 런타임 잠금을 제약으로 받는다.
_PAIRS = (
    ("requirements.in", "requirements.txt"),
    ("requirements-dev.in", "requirements-dev.txt"),
)

# 입력 한 줄의 모양. **이 두 모양 밖이면 떨어진다** — 마커나 URL 을 조용히
# 건너뛰면 그 줄이 견주기 밖에 선다.
_INPUT_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[([A-Za-z0-9,._-]+)\])?==(\S+)")
_INPUT_INCLUDE = re.compile(r"-r\s+(\S+)")
# 제약은 입력이 아니라 잠금을 가리킨다 — 고정을 더하지 않는다.
_INPUT_CONSTRAINT = re.compile(r"-c\s+\S+")

# 잠금 한 항목의 머리 — `name==version \`.
_LOCK_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+) \\$")
# 그 항목을 무엇이 불렀는가 — `# via -r 입력` · `#   -c 잠금` · `#   패키지`.
_LOCK_VIA = re.compile(r"\s*#\s+(?:via\s+)?(-[rc] \S+|[A-Za-z0-9][A-Za-z0-9._-]*)")

# 요구 한 줄의 이름과, 마커가 그것을 거는 extra.
_REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_MARKER_EXTRA = re.compile(r"extra\s*==\s*(['\"])(.+?)\1")


def _normalize(name: str) -> str:
    """PEP 503 의 이름 정규화 — `SQLAlchemy` 와 `sqlalchemy` 는 같은 패키지다."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _input(name: str) -> dict[str, tuple[str, frozenset[str]]]:
    """입력 파일이 **직접** 고정한 것 — 이름마다 (버전, 고른 extra). `-r` 을 따라간다."""
    pins: dict[str, tuple[str, frozenset[str]]] = {}
    for raw in (BACKEND_ROOT / name).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if include := _INPUT_INCLUDE.fullmatch(line):
            pins |= _input(include.group(1))
            continue
        if _INPUT_CONSTRAINT.fullmatch(line):
            continue
        pin = _INPUT_PIN.fullmatch(line)
        assert pin, f"{name}: 이 검사가 읽지 못하는 줄이다 — {line!r}"
        extras = frozenset(_normalize(e) for e in (pin.group(2) or "").split(",") if e)
        pins[_normalize(pin.group(1))] = (pin.group(3), extras)
    return pins


def _lock(name: str) -> tuple[dict[str, str], dict[str, set[str]]]:
    """잠금의 전체 고정 · 그리고 항목마다 **무엇이 불렀는가**(pip-compile 의 `# via`)."""
    pins: dict[str, str] = {}
    via: dict[str, set[str]] = {}
    current = ""
    for line in (BACKEND_ROOT / name).read_text().splitlines():
        if head := _LOCK_PIN.match(line):
            current = _normalize(head.group(1))
            pins[current] = head.group(2)
            via[current] = set()
        elif current and (by := _LOCK_VIA.fullmatch(line)) and by.group(1) != "via":
            via[current].add(by.group(1))
    return pins, via


def _direct(via: dict[str, set[str]]) -> set[str]:
    """잠금에 **입력이 직접 부른다**(`-r`)고 적힌 것."""
    return {name for name, by in via.items() if any(b.startswith("-r ") for b in by)}


def _parents(by: set[str]) -> set[str]:
    """`# via` 가운데 패키지인 것 — 입력 · 잠금을 가리키는 줄은 뺀다."""
    return {_normalize(b) for b in by if not b.startswith("-")}


def _extra_deps(package: str) -> dict[str, set[str]]:
    """설치된 `package` 의 extra 마다 **그 extra 때문에** 더 부르는 것.

    extra 없이도 부르는 것은 뺀다 — SQLAlchemy 는 `greenlet` 을 플랫폼 마커로 늘
    부르고 `asyncio` 같은 extra 에서도 다시 부른다. 그것은 extra 의 몫이 아니다.
    """
    always: set[str] = set()
    found: dict[str, set[str]] = {
        _normalize(extra): set() for extra in metadata(package).get_all("Provides-Extra") or []
    }
    for spec in requires(package) or []:
        head = _REQUIREMENT_NAME.match(spec)
        assert head, spec
        name = _normalize(head.group(0))
        extras = [extra for _, extra in _MARKER_EXTRA.findall(spec)]
        if not extras:
            always.add(name)
        for extra in extras:
            found.setdefault(_normalize(extra), set()).add(name)
    return {extra: deps - always for extra, deps in found.items()}


def test_every_pin_in_the_input_is_the_pin_in_the_lock() -> None:
    """**입력을 고치고 잠금을 다시 만들지 않으면 떨어진다.**

    설치는 잠금에서 하므로, 입력의 버전만 올리면 **아무것도 바뀌지 않은 채
    초록이다** — 사람은 올렸다고 믿는다. 거꾸로 입력에서 지운 패키지가 잠금에
    「입력이 부른다」로 남으면 지운 것이 계속 깔린다. 두 방향을 다 본다.
    """
    for source, lock in _PAIRS:
        wanted = {name: version for name, (version, _) in _input(source).items()}
        locked, via = _lock(lock)

        drifted = {
            name: (version, locked.get(name))
            for name, version in wanted.items()
            if locked.get(name) != version
        }
        assert drifted == {}, f"{source} 와 {lock} 가 갈렸다(입력, 잠금): {drifted}"

        orphaned = sorted(_direct(via) - wanted.keys())
        assert orphaned == [], f"{lock} 에 입력이 부르지 않는 직접 의존성이 남았다: {orphaned}"


def test_the_extras_the_input_picks_are_the_extras_the_lock_carries() -> None:
    """**입력에서 extra 를 떼거나 붙이고 잠금을 다시 만들지 않으면 떨어진다.**

    잠금은 `--strip-extras` 로 풀려 `psycopg[binary]` 가 아니라 `psycopg` 와
    `psycopg-binary` 두 줄로 남는다. 그래서 버전만 견주면 입력의 `[binary]` 를 떼도
    **초록이고, 뗀 패키지가 계속 깔린다**(ERP#22 의 Codex 리뷰가 짚었고 재현했다).
    두 방향을 본다 — 고른 extra 가 부르는 것이 잠금에 없는 것, 고르지 않은 extra 가
    부르는 것이 **그 패키지 하나 때문에만** 잠금에 남은 것.
    """
    for source, lock in _PAIRS:
        locked, via = _lock(lock)
        missing: dict[str, list[str]] = {}
        stale: dict[str, list[str]] = {}
        for name, (_, picked) in _input(source).items():
            for extra, deps in _extra_deps(name).items():
                if extra in picked:
                    if gone := sorted(deps - locked.keys()):
                        missing[f"{name}[{extra}]"] = gone
                    continue
                # 고르지 않은 extra 의 것이 **이 패키지 하나 때문에만** 남았다
                only_here = [d for d in deps & locked.keys() if _parents(via[d]) == {name}]
                if only_here:
                    stale[f"{name}[{extra}]"] = sorted(only_here)

        assert missing == {}, f"{source} 가 고른 extra 의 의존성이 {lock} 에 없다: {missing}"
        assert stale == {}, f"{source} 가 떼어 낸 extra 의 의존성이 {lock} 에 남았다: {stale}"


def test_the_runtime_lock_and_the_dev_lock_agree() -> None:
    """**검사가 도는 환경과 이미지가 도는 환경이 같은 버전이다.**

    둘을 따로 풀면 하위 의존성이 날마다 달리 올 수 있다 — 「환경에 따라 다르게
    도는 검사는 검사가 아니다」(`requirements.in` 의 starlette 사고). 개발 입력이
    런타임 잠금을 제약(`-c`)으로 받아 풀리므로 겹치는 것은 같아야 한다.
    """
    runtime, _ = _lock("requirements.txt")
    dev, _ = _lock("requirements-dev.txt")

    differs = {
        name: (version, dev.get(name))
        for name, version in runtime.items()
        if dev.get(name) != version
    }
    assert differs == {}, f"런타임 잠금과 개발 잠금이 갈렸다(런타임, 개발): {differs}"


def test_the_image_and_ci_install_from_the_lock_with_hashes() -> None:
    """**설치하는 두 자리가 잠금을 해시로 읽는다.**

    잠금이 있어도 설치가 입력을 읽으면 아무것도 지키지 않는다 — 그리고 그렇게
    되돌려도 빌드도 테스트도 초록이다.
    """
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text()
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()

    assert re.search(r"pip install .*--require-hashes -r requirements\.txt\b", dockerfile)
    assert re.search(r"pip install .*--require-hashes -r requirements-dev\.txt\b", ci)
