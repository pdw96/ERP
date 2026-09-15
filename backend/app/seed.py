"""기준정보를 심는다 — 세 조건을 모두 통과할 때만.

「DB 파일이 없으면 시드한다」는 PostgreSQL 에서 성립하지 않는다. 지울 파일이
없기 때문이다. 대신할 것은 하나가 아니라 셋이다:

1. **표를 먼저 맞춘다** — 마이그레이션을 끝까지 돌린다. 판단이 아니라 전제이며,
   표가 없으면 「비어 있는지」를 물어볼 수조차 없다. 셸이 먼저 한다.
2. **스위치가 켜져 있어야 한다** — 운영에서 자동 시드는 사고이지 편의가 아니다.
3. **품목 표가 비어 있어야 한다** — 「표가 있는가」는 아무것도 말해 주지 않는다.
   마이그레이션이 항상 만들어 두기 때문이다. 물어야 할 것은 **내용의 유무**다.

왜 하필 품목 표인가. 가장 먼저 채워지고 마지막까지 남는 표이기 때문이다.
로트나 실적 같은 거래 표는 비어 있는 것이 정상 상태라 표식이 될 수 없다.
"""

import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core import locks
from app.core.config import get_settings
from app.db.base import create_db_engine

SEED_DIR = Path(__file__).parent / "seed_data"

# 시드 구간을 감싸는 잠금. **컨테이너가 둘 이상 동시에 뜨면 둘 다 「비어 있다」를
# 보고 둘 다 넣는다** — 파일 하나였을 때는 없던 문제이며, PostgreSQL 이라서
# 생긴다. 트랜잭션이 끝나면 저절로 풀린다.
_LOCK_KEY = locks.SEED


def seed(engine: Engine) -> bool:
    """기준정보를 넣는다. 실제로 넣었으면 True, 건너뛰었으면 False.

    **전체가 트랜잭션 하나다.** 중간에 터지면 아무것도 들어가지 않은 상태로
    되돌아가고 다음 기동에서 다시 시도된다. 「반쯤 채워짐」이라는 상태 자체를
    없애는 것이 목적이다 — 반쯤 채워진 데이터베이스는 「비어 있지 않다」로
    판정되어 다시는 시드되지 않고, 고장난 채로 영원히 굳는다.
    """
    if not get_settings().seed_enabled:
        return False

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})

        if conn.execute(text("SELECT count(*) FROM items")).scalar_one():
            return False

        # **드라이버 커서로 직접 보낸다.** SQLAlchemy 를 거치면 psycopg 가 SQL 의
        # `%` 를 플레이스홀더로 읽는데, 이 시드에는 단위가 퍼센트인 검사 항목이
        # 있다(수분 · 배합비). 데이터를 코드 편의에 맞춰 바꾸지 않는다 — 파라미터
        # 없이 보내면 psycopg 가 `%` 를 건드리지 않는다.
        #
        # 같은 트랜잭션 안이므로 중간에 터지면 앞 파일이 넣은 것도 함께 되돌아간다.
        cursor = conn.connection.dbapi_connection.cursor()  # type: ignore[union-attr]
        try:
            for path in sorted(SEED_DIR.glob("*.sql")):
                cursor.execute(path.read_text(encoding="utf-8"))
        finally:
            cursor.close()

    return True


def main() -> int:
    engine = create_db_engine()
    try:
        planted = seed(engine)
    finally:
        engine.dispose()

    if planted:
        print("기준정보를 심었다")
    else:
        print("건너뛰었다 — 스위치가 꺼져 있거나 품목 표가 이미 차 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
