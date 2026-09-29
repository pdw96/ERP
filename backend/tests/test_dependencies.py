"""의존성은 **잠금 파일**에서 해시까지 맞춰 설치한다 — 감사 ⑳ 이 넘긴 「의존성 무결성」.

`requirements.txt` · `requirements-dev.txt` 는 **사람이 고치는 입력**이다. 무엇을
왜 쓰는지 적는 자리이고, 하위 의존성까지 고정하지는 않는다. 설치는
`requirements.lock` · `requirements-dev.lock` 에서 `--require-hashes` 로 한다 —
하위 의존성까지 버전과 해시가 박혀 있어 **같은 이름 · 같은 버전으로 다른 파일이
오면 설치가 멈춘다.**

입력과 잠금은 **두 벌**이다. 합칠 수 없으므로(입력에 해시를 적으면 사람이 고칠
수 없다) 견주는 검사가 그 자리를 대신한다 — 「목록을 두 벌 두지 않는다. 두 벌이면
반드시 갈린다」.

**이 파일이 못 보는 부류**(W-6 ③):

- **처음부터 엉뚱한 패키지를 고른 것.** 해시는 「처음 받은 그 파일」을 지킬 뿐이라
  이름을 잘못 적은 패키지(타이포스쿼팅)도 충실히 잠근다. 의존성을 더하는 날
  사람이 본다.
- **잠금이 리눅스 · 파이썬 3.12 에서 풀렸다는 것.** CI 와 이미지는 그 환경이다.
  다른 플랫폼에서만 붙는 의존성은 잠금에 없어 그 자리에서 설치가 멈춘다 —
  조용히 통과하지는 않는다.
- **잠금의 하위 의존성이 입력에서 실제로 나오는가.** 풀이를 다시 하지 않으므로
  「입력이 직접 부른다」고 적힌 줄만 입력과 견준다.
"""

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

# 입력 → 잠금. 개발 입력은 `-r requirements.txt` 로 런타임 입력을 품는다.
_PAIRS = (
    ("requirements.txt", "requirements.lock"),
    ("requirements-dev.txt", "requirements-dev.lock"),
)

# 입력 한 줄의 모양. **이 두 모양 밖이면 떨어진다** — 마커나 URL 을 조용히
# 건너뛰면 그 줄이 견주기 밖에 선다.
_INPUT_PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9,._-]+\])?==(\S+)")
_INPUT_INCLUDE = re.compile(r"-r\s+(\S+)")

# 잠금 한 항목의 머리 — `name==version \`.
_LOCK_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+) \\$")


def _normalize(name: str) -> str:
    """PEP 503 의 이름 정규화 — `SQLAlchemy` 와 `sqlalchemy` 는 같은 패키지다."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _input_pins(name: str) -> dict[str, str]:
    """입력 파일이 **직접** 고정한 것. `-r` 을 따라간다."""
    pins: dict[str, str] = {}
    for raw in (BACKEND_ROOT / name).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if include := _INPUT_INCLUDE.fullmatch(line):
            pins |= _input_pins(include.group(1))
            continue
        pin = _INPUT_PIN.fullmatch(line)
        assert pin, f"{name}: 이 검사가 읽지 못하는 줄이다 — {line!r}"
        pins[_normalize(pin.group(1))] = pin.group(2)
    return pins


def _lock(name: str) -> tuple[dict[str, str], set[str]]:
    """잠금의 전체 고정 · 그리고 그 가운데 **입력이 직접 부른다**고 적힌 것."""
    pins: dict[str, str] = {}
    direct: set[str] = set()
    current = ""
    for line in (BACKEND_ROOT / name).read_text().splitlines():
        if head := _LOCK_PIN.match(line):
            current = _normalize(head.group(1))
            pins[current] = head.group(2)
        elif current and re.fullmatch(r"\s*#\s+(?:via\s+)?-r \S+", line):
            direct.add(current)
    return pins, direct


def test_every_pin_in_the_input_is_the_pin_in_the_lock() -> None:
    """**입력을 고치고 잠금을 다시 만들지 않으면 떨어진다.**

    설치는 잠금에서 하므로, 입력의 버전만 올리면 **아무것도 바뀌지 않은 채
    초록이다** — 사람은 올렸다고 믿는다. 거꾸로 입력에서 지운 패키지가 잠금에
    「입력이 부른다」로 남으면 지운 것이 계속 깔린다. 두 방향을 다 본다.
    """
    for source, lock in _PAIRS:
        wanted = _input_pins(source)
        locked, direct = _lock(lock)

        drifted = {
            name: (version, locked.get(name))
            for name, version in wanted.items()
            if locked.get(name) != version
        }
        assert drifted == {}, f"{source} 와 {lock} 가 갈렸다(입력, 잠금): {drifted}"

        orphaned = sorted(direct - wanted.keys())
        assert orphaned == [], f"{lock} 에 입력이 부르지 않는 직접 의존성이 남았다: {orphaned}"


def test_the_runtime_lock_and_the_dev_lock_agree() -> None:
    """**검사가 도는 환경과 이미지가 도는 환경이 같은 버전이다.**

    둘을 따로 풀면 하위 의존성이 날마다 달리 올 수 있다 — 「환경에 따라 다르게
    도는 검사는 검사가 아니다」(`requirements.txt` 의 starlette 사고). 개발 잠금은
    런타임 잠금을 제약(`-c`)으로 받아 풀므로 겹치는 것은 같아야 한다.
    """
    runtime, _ = _lock("requirements.lock")
    dev, _ = _lock("requirements-dev.lock")

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

    assert re.search(r"pip install .*--require-hashes -r requirements\.lock\b", dockerfile)
    assert re.search(r"pip install .*--require-hashes -r requirements-dev\.lock\b", ci)
