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
