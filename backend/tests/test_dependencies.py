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
from pathlib import Path

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
# 2026-09-30). 룰셋은 잡 이름(`backend`)만 걸므로 이 목록이 스텝의 존재를 무는 유일한 자리다.
# 스텝을 더하면 여기도 더한다 — 빠진 스텝은 이 검사가 보지 않는다(아래 「못 보는 부류」).
_CI_STEPS = {
    "의존성": r"pip install --require-hashes -r requirements-dev\.txt",
    "잠금": r"scripts/lock\.sh --check",
    "린트": r"ruff check \.",
    "포맷": r"ruff format --check \.",
    "타입체크": r"mypy app migrations",
    "테스트": r"pytest",
    "셸": r"shellcheck",
    "이미지": r"docker build ",
    "기동": r"curl -fsS -o /dev/null -X POST ",
}


def _backend_steps(ci: str) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """`ci.yml` 의 `jobs.backend` 와 그 스텝(이름 → 스텝) — **YAML 파서가 읽는다.**

    룰셋이 거는 잡이 `backend` 라 그 잡만 본다. 처음에는 손으로 줄을 갈랐는데 형제 잡의 스텝이
    빈자리를 채우고, `env:` 에 남긴 글자가 명령으로 읽히고, 접힌 블록(`run: >`)이 YAML 과 다르게
    이어지고, 형제 잡의 `if:` 가 거짓 양성을 냈다 — 리뷰 세 라운드가 연달아 틈을 짚었다(PR #38).
    저장소 소유자가 파서로 바꾸기로 정했다(2026-09-30 — `docs/리뷰-루프.md` 방안 A).
    """
    job = yaml.safe_load(ci)["jobs"]["backend"]
    steps = {step["name"]: step for step in job["steps"] if "name" in step}
    return job, steps


def test_every_check_step_is_still_there_and_can_still_fail() -> None:
    """**CI 의 검사 스텝이 서 있고, 떨어질 수 있다** (감사 ㉕ OB-2).

    머지를 막는 것은 `backend` 잡의 **이름**이다. 그래서 그 잡 안의 린트 · 타입 · 테스트 ·
    셸 · 이미지 · 기동 스텝을 지우거나 `continue-on-error: true` 를 달아도 잡은 초록이고
    머지가 된다 — 실제로 돌려 확인했다(감사 ㉕ M6-d). 위 검사가 의존성 · 잠금 줄만 물던
    자리를 스텝 전부로 넓힌다: `backend` 잡의 스텝마다 **`run` 값에 명령이 있고**, 실패를
    삼키는 장치(잡과 스텝의 `continue-on-error` · `if:`, 명령의 `|| true`)가 **없다.**

    **이 검사가 못 보는 부류**(W-6 ③): 명령의 **인자**가 좁아진 것(`pytest tests/test_api.py`
    처럼 — 명령은 있다), 위 목록에 없는 새 스텝, 셸 안에서 실패를 삼키는 다른 모양
    (`set +e` · `; true`), 그리고 워크플로 밖(룰셋 · 저장소 설정)에서 검사를 끄는 것.
    """
    workflows = REPO_ROOT / ".github" / "workflows"
    job, steps = _backend_steps((workflows / "ci.yml").read_text())
    assert steps, "backend 잡에서 스텝을 찾지 못했다 — 이 검사가 아무것도 세지 않는다"

    missing = [
        name
        for name, command in _CI_STEPS.items()
        if name not in steps or not re.search(command, str(steps[name].get("run", "")))
    ]
    assert missing == [], f"backend 잡에서 검사 스텝이나 그 run 명령이 사라졌다: {missing}"

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
    swallowing += [
        f"{path.name}: continue-on-error"
        for path in sorted(workflows.glob("*.yml"))
        if re.search(r"^\s*continue-on-error:", path.read_text(), re.M)
    ]
    assert swallowing == [], "CI 가 실패를 삼키는 자리가 있다:\n" + "\n".join(swallowing)
