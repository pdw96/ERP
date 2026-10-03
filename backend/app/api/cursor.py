"""목록을 넘기는 커서 — **목록마다 한 벌씩 짓지 않고 여기 하나다**(ADR 0020).

커서는 부르는 쪽이 해석하지 않는 문자열이다. 속은 계약이 아니지만
**이미 내준 커서를 받지 못하게 되는 것은 깨는 변경이다** — 넘기는 도중의
부르는 쪽이 남은 줄을 받지 못한다. 그래서 커서는 자기 판을 들고, 판은 모양만이
아니라 **그 목록의 정렬과 거름의 뜻까지** 든다. 같은 앞자리 동안 내준 판은 모두
읽는다.

판 `v1` — 대리키 순서, 거름은 「재검사를 기다리는가」 하나. 속은
`{"a": 거름, "id": 마지막 대리키}` 를 URL 에 실을 수 있게 base64url 로 싼 것이다.
"""

import base64
import binascii
import json
from dataclasses import dataclass

_VERSION = "v1"


class UnreadableCursor(ValueError):
    """이 판이 내준 적 없는 모양이다 — 망가졌거나 다른 판의 것이다."""


@dataclass(frozen=True)
class LotCursor:
    """로트 목록의 어디까지 읽었나."""

    awaiting_retest: bool
    after: int


def issue(cursor: LotCursor) -> str:
    body = json.dumps({"a": cursor.awaiting_retest, "id": cursor.after}, separators=(",", ":"))
    packed = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{_VERSION}.{packed}"


def read(token: str) -> LotCursor:
    version, _, packed = token.partition(".")
    if version != _VERSION or not packed:
        raise UnreadableCursor(token)
    try:
        body = json.loads(base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4)))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnreadableCursor(token) from exc
    if not isinstance(body, dict):
        raise UnreadableCursor(token)
    awaiting, after = body.get("a"), body.get("id")
    if not isinstance(awaiting, bool) or isinstance(after, bool) or not isinstance(after, int):
        raise UnreadableCursor(token)
    if after <= 0:
        raise UnreadableCursor(token)
    return LotCursor(awaiting_retest=awaiting, after=after)
