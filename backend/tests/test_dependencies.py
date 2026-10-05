"""의존성은 **잠금 파일**에서 해시까지 맞춰 설치한다 — 감사 ⑳ 이 넘긴 「의존성 무결성」.

`requirements.in` · `requirements-dev.in` 은 **사람이 고치는 입력**이다. 무엇을
왜 쓰는지 적는 자리이고, 하위 의존성까지 고정하지는 않는다. 설치는 잠금
`requirements.txt` · `requirements-dev.txt` 에서 `--require-hashes` 로 한다 —
하위 의존성까지 버전과 해시가 박혀 있어 **같은 이름 · 같은 버전으로 다른 파일이
오면 설치가 멈춘다.**

**입력과 잠금이 갈리는지는 이 파일이 보지 않는다.** CI 의 「잠금」 스텝이
`scripts/lock.sh --check` 로 잠금을 입력에서 **다시 만들어** 견준다(ERP#22).
한때 이 파일이 pip 의 풀이(extra · 버전 · 하위 의존성)를 손으로 흉내 내 견줬는데,
고칠 때마다 새 틈이 났다(ERP#22 리뷰 1 · 2 라운드). 흉내 대신 잠금을 만드는
도구 자신에게 묻는다 — 그 스텝은 네트워크가 있어야 해서 여기가 아니라 CI 에 선다.

**이 파일이 못 보는 부류**(W-6 ③): 처음부터 엉뚱한 패키지를 고른 것. 해시는 「처음
받은 그 파일」을 지킬 뿐이라 이름을 잘못 적은 패키지(타이포스쿼팅)도 충실히 잠근다.
의존성을 더하는 날 사람이 본다.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def test_the_image_and_ci_install_from_the_lock_and_check_it() -> None:
    """**설치하는 두 자리가 잠금을 해시로 읽고, CI 가 잠금을 다시 만들어 견준다.**

    잠금이 있어도 설치가 입력을 읽으면 아무것도 지키지 않는다 — 그리고 그렇게
    되돌려도 빌드도 테스트도 초록이다. 견주는 스텝이 빠져도 마찬가지로 초록이다.
    """
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text()
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()

    assert re.search(r"pip install .*--require-hashes -r requirements\.txt\b", dockerfile)
    assert re.search(r"pip install .*--require-hashes -r requirements-dev\.txt\b", ci)
    assert re.search(r"pip install .*--require-hashes -r requirements-tools\.txt\b", ci)
    assert re.search(r"^\s+scripts/lock\.sh --check$", ci, re.MULTILINE)


# **CI 의 검사 스텝과 그 스텝이 부르는 명령**(감사 ㉕ OB-2 — 저장소 소유자가 넓히기로 정했다,
# 2026-09-30). 룰셋이 CI 에서 거는 상태 체크는 잡 이름(`backend`)이라 — 스텝 하나하나는 룰셋이
# 모른다 — 이 목록이 스텝의 존재를 무는 유일한 자리다. CodeQL 결과도 머지를 막지만(ADR 0005)
# 그것은 따로 선 워크플로의 결과다. **목록은 `ci.yml` 의 사본이라 두 방향으로 견준다**(감사 ㉘
# NC-211) — `run` 스텝을 더하고 여기 더하지 않으면 아래 검사가 빨개진다.
# **명령은 `run` 안에서 줄의 맨 앞에 선다** — 주석(`#`)이나 `echo` 뒤에 선 글자는 명령이
# 아니다(저장소 소유자가 정한 작성 규칙, 2026-09-30 — `docs/리뷰-루프.md` 방안 B). 「줄」은
# **물리적 줄**이다(아래 `_executable_lines`).
_CI_STEPS = {
    "의존성": r"pip install --require-hashes -r requirements-dev\.txt",
    "잠금": r"scripts/lock\.sh --check",
    "린트": r"ruff check \.",
    "포맷": r"ruff format --check \.",
    "타입체크": r"mypy$",
    "계약의 기준": r"git fetch --no-tags --depth=1 origin",
    "테스트": r"pytest",
    "판정 분기": r"coverage report$",
    "셸": r"git ls-files .*\| xargs .*shellcheck",
    "이미지": r"docker build ",
    "기동": r"curl -fsS -o /dev/null -X POST ",
}


def _backend_steps(ci: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """`ci.yml` 의 `jobs.backend` 와 그 스텝(이름 → 스텝) — **YAML 파서가 읽는다.**

    룰셋이 CI 에서 거는 상태 체크가 `backend` 잡이라 그 잡만 본다(CodeQL 은 따로 선
    워크플로다). 처음에는 손으로 줄을 갈랐는데 형제 잡의 스텝이
    빈자리를 채우고, `env:` 에 남긴 글자가 명령으로 읽히고, 접힌 블록(`run: >`)이 YAML 과 다르게
    이어지고, 형제 잡의 `if:` 가 거짓 양성을 냈다 — 리뷰 세 라운드가 연달아 틈을 짚었다(PR #38).
    저장소 소유자가 파서로 바꾸기로 정했다(2026-09-30 — `docs/리뷰-루프.md` 방안 A).
    """
    job = yaml.safe_load(ci)["jobs"]["backend"]
    steps = {step["name"]: step for step in job["steps"] if "name" in step}
    return job, steps


def _executable_lines(step: dict[str, object]) -> list[str]:
    """스텝의 `run` 을 **물리적 줄**로 나눈 것 — 앞뒤 공백을 벗기고, 빈 줄과 주석 줄은 뺀다.

    셸이 실제로 실행하는 단위가 아니다(감사 ㉘ NC-210). 줄 끝의 `\\` 로 이어진 줄과 따옴표 안의
    줄도 저마다 한 줄이다 — 잠금 스텝의 `scripts/lock.sh --check` 도 앞 줄에서 이어진 둘째 줄로
    읽혀 통과한다. 그래서 `echo \\` 다음 줄에 명령을 두면 셸은 `echo` 만 돌리는데 이 검사는
    명령이 있다고 읽는다(아래 검사의 「못 보는 부류」).
    """
    return [
        line.strip()
        for line in str(step.get("run", "")).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _swallowing_jobs(workflows: Path) -> list[str]:
    """모든 워크플로(`.yml` · `.yaml`)의 잡과 스텝에 걸린 `continue-on-error` — YAML 로 읽는다.

    줄 검색으로 찾으면 키에 따옴표를 붙인 `"continue-on-error"` 가 빠졌다(PR #38 Codex 리뷰).
    """
    found: list[str] = []
    for path in sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]):
        for name, job in (yaml.safe_load(path.read_text()).get("jobs") or {}).items():
            if "continue-on-error" in job:
                found.append(f"{path.name}: {name} 잡의 continue-on-error")
            found += [
                f"{path.name}: {name} 잡의 스텝 {step.get('name', '?')} 의 continue-on-error"
                for step in job.get("steps") or []
                if "continue-on-error" in step
            ]
    return found


def test_every_check_step_is_still_there_and_can_still_fail() -> None:
    """**CI 의 검사 스텝이 서 있고, 떨어질 수 있다** (감사 ㉕ OB-2).

    CI 에서 머지를 막는 상태 체크는 `backend` 잡의 **이름**이다 — 잡 안의 스텝은 룰셋이 모른다.
    **돌려 확인한 것**은 하나다: 잠금 스텝에 `continue-on-error: true` 를 달아도 그때의 검사가
    초록이었다(감사 ㉕ M6-d). 다른 스텝을 지우거나 끄는 것, 그리고 그때 잡이 초록이고 머지가
    된다는 것은 **읽어서 판단한 것**이다 — 스텝의 실패를 삼키면 잡이 실패하지 않는다는 GitHub
    Actions 의 정의에서 온다(감사 ㉘ NC-212). 위 검사가 의존성 · 잠금 줄만 물던 자리를 스텝
    전부로 넓힌다: **목록의** 스텝마다 **`run` 값에 명령이 있고**, `backend` 잡의 `run` 스텝이
    전부 목록에 들며, 실패를 삼키는 장치(잡과 스텝의 `continue-on-error` · `if:`, 명령의
    `|| true`)가 **없다.**

    명령은 `run` 의 **물리적 줄 맨 앞**에서 찾는다 — 주석으로 막거나 `echo` 로 찍기만 한 명령은
    명령이 아니다(PR #38 Codex 리뷰 · 저장소 소유자가 정한 작성 규칙 — `docs/리뷰-루프.md`
    방안 B).

    **이 검사가 못 보는 부류**(W-6 ③): 명령의 **인자**가 좁아진 것(`pytest tests/test_api.py`
    처럼 — 명령은 있다), 셸 안에서 실패를 삼키는 다른 모양(`set +e` · `; true` ·
    `if false; then …`), 줄 끝의 `\\` 로 앞 줄에 이어 붙인 명령(`echo \\` 다음 줄 — 물리적 줄로
    읽는다, 감사 ㉘ NC-210), 그리고 워크플로 밖(룰셋 · 저장소 설정)에서
    검사를 끄는 것. **이 검사는 실수로 지우거나 끄는 것을 막는다 — 일부러 속이려는 편집은 막지
    않는다.** 셸은 튜링 완전해서 글자로는 끝까지 가를 수 없고, 그 자리는 diff 를 보는 사람이다.
    """
    workflows = REPO_ROOT / ".github" / "workflows"
    job, steps = _backend_steps((workflows / "ci.yml").read_text())
    assert steps, "backend 잡에서 스텝을 찾지 못했다 — 이 검사가 아무것도 세지 않는다"

    missing = [
        name
        for name, command in _CI_STEPS.items()
        if name not in steps
        or not any(re.match(command, line) for line in _executable_lines(steps[name]))
    ]
    assert missing == [], f"backend 잡에서 검사 스텝이나 그 run 명령이 사라졌다: {missing}"

    # **반대 방향**(감사 ㉘ NC-211) — 목록은 `ci.yml` 의 사본이라 한 방향만 견주면 새 스텝이
    # 목록 밖에 선다. `run` 스텝은 전부 이름이 있고 목록에 든다(`uses` 스텝은 검사 스텝이
    # 아니다)
    unlisted = [
        str(step.get("name", "(이름 없는 run 스텝)"))
        for step in job["steps"]
        if "run" in step and step.get("name") not in _CI_STEPS
    ]
    assert unlisted == [], (
        f"backend 잡의 run 스텝이 _CI_STEPS 에 없다 — 목록에 더한다: {unlisted}"
    )

    # 이름으로 모으면 같은 이름의 스텝이 하나로 접힌다 — 진짜 `린트` 앞에 `echo` 만 하는
    # `린트` 를 두어도 초록이었다(PR #39 Codex 리뷰). `run` 스텝의 이름은 겹치지 않는다
    names = [step.get("name") for step in job["steps"] if "run" in step]
    twice = sorted({str(name) for name in names if names.count(name) > 1})
    assert twice == [], f"backend 잡의 run 스텝 이름이 겹쳐 하나로 접힌다: {twice}"

    # **잡 자체를 끄는 것도 삼킨다**(PR #38 Codex 리뷰). 잡의 `if:` 가 거짓이면 스텝은 한 줄도
    # 돌지 않은 채 건너뛴 잡이 된다 — 스텝의 글자는 그대로다
    swallowing = [f"backend 잡의 {key}" for key in ("if", "continue-on-error") if key in job]
    swallowing += [
        f"{name}: {key}"
        for name, step in steps.items()
        for key in ("if", "continue-on-error")
        if key in step
    ]
    swallowing += [
        f"{name}: || true"
        for name, step in steps.items()
        if re.search(r"\|\|\s*true\b", str(step.get("run", "")))
    ]
    swallowing += _swallowing_jobs(workflows)
    assert swallowing == [], "CI 가 실패를 삼키는 자리가 있다:\n" + "\n".join(swallowing)


def test_the_type_check_covers_every_gate_file() -> None:
    """**타입 검사의 범위가 앱 · 마이그레이션과 게이트 파일 전부를 든다** (감사 ㉙ — ADR 0007).

    범위는 `pyproject.toml` 의 `[tool.mypy] files` 한 자리이고, CI 와 로컬은 인자 없이 `mypy` 를
    부른다(인자를 주면 `files` 를 덮는다 — 그래서 위 검사가 `타입체크` 스텝의 명령을 `mypy` 한
    낱말로 문다). 게이트 파일의 목록은 `tests/test_prose.py` 의 `_GATE_FILES` 라 **두 벌**이다 —
    게이트 파일이 새로 서서 `_GATE_FILES` 에 들고 `files` 에 들지 않으면 여기서 빨개진다.

    **이 검사가 못 보는 부류**(W-6 ③): `_GATE_FILES` 에 들지 않은 게이트 파일(그 목록의
    「못 보는 부류」와 같다), 그리고 `files` 에 든 경로가 실제로 타입 검사를 **통과하는지** —
    그것은 `타입체크` 스텝이 문다.
    """
    from tests.test_prose import _GATE_FILES

    config = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text())
    files = config["tool"]["mypy"].get("files", [])
    assert files, "[tool.mypy] files 가 비었다 — 인자 없는 mypy 가 무엇을 볼지 정해지지 않는다"

    missing = [path for path in ("app", "migrations", *_GATE_FILES) if path not in files]
    assert missing == [], f"타입 검사의 범위([tool.mypy] files)에 없다: {missing}"


def test_the_judgment_module_keeps_its_branch_floor() -> None:
    """**판정 모듈의 분기 커버리지 하한이 그대로 있다** (ADR 0024 — 4단계 조각 1).

    하한은 `pyproject.toml` 의 `[tool.coverage]` 한 자리가 든다. 위 검사는 「판정 분기」 스텝의
    `coverage report` 가 있는 것만 문다 — 설정에서 하한을 내리거나 · 분기를 끄거나 · 범위를
    넓혀 다른 모듈의 줄로 메워도 그 명령은 그대로 초록이다. 그래서 설정의 세 값과, 그 스텝이
    **판정 테스트를** 돌려 재는 것을 여기서 문다.

    **이 검사가 못 보는 부류**(W-6 ③): 판정 모듈 안에서 빼는 표시(`pragma: no cover`)로 분기를
    덮는 것 — 설정이 아니라 코드의 글자다. 그 자리는 diff 를 보는 사람이다(`pyproject.toml` 의
    주석이 「덮지 않고 걷어 낸다」를 든다).
    """
    config = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text())["tool"]["coverage"]
    assert config["run"].get("branch") is True, "분기가 아니라 줄을 잰다"
    assert config["run"].get("source") == ["app.api.compat"], config["run"].get("source")
    assert config["report"].get("fail_under") == 100, config["report"].get("fail_under")

    _, steps = _backend_steps((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    lines = _executable_lines(steps["판정 분기"])
    assert lines.index("coverage run -m pytest tests/test_contract_judgment.py") < lines.index(
        "coverage report"
    ), lines
