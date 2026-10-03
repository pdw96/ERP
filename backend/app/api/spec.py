"""**밖으로 나가는 계약의 사진** — `docs/openapi.json` 을 짓고 테스트가 견준다(ADR 0012).

`/openapi.json` 은 실행할 때 지어져 저장소에 없었다. 그래서 오류 이름이나 응답 선언을 바꾸는
PR 에서 리뷰어가 보는 것은 `schemas.py` 의 한 줄이었지 **밖으로 나가는 계약의 변화**가
아니었다(감사 ⑯ · ㉛ OB-1). 사진을 저장소에 두고 실제 스펙과 견주면, 계약을 바꾸는 커밋은
사진을 다시 지어야 초록이 되고 그 변화가 diff 에 그대로 남는다.

**이것은 막지 않고 보이게 한다.** 깨는 변경인지 가르고 판이 모자라면 막는 것은 그 옆에 따로
선 판정이다(`app/api/compat.py` · `tests/test_contract_judgment.py`, ADR 0018) — 이 사진은
변경마다 다시 지어지므로 옛 계약은 들어갈 자리의 사진에서 꺼낸다.

다시 짓는다:

    cd backend && .venv/bin/python -m app.api.spec
"""

import json
from pathlib import Path

from app.api.app import app

# 저장소 안에서만 쓴다 — 이미지에는 `docs/` 가 없다
SNAPSHOT = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"


def render() -> str:
    """**같은 스펙은 같은 글자다.**

    키를 정렬해, 선언 순서가 아니라 계약이 바뀔 때만 diff 가 난다.
    """
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SNAPSHOT.write_text(render(), encoding="utf-8")
