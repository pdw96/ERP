"""표가 사는 곳.

**모든 모델 모듈을 여기서 불러들인다.** `Base.metadata` 가 표를 알려면 그
모듈이 한 번은 import 되어야 하고, 그 자리를 한 곳으로 모아 두지 않으면
마이그레이션이 「모델에는 있는데 표가 없는」 상태를 조용히 만든다.

조각이 하나 설 때마다 여기 한 줄이 는다.
"""

from app.db import common_codes as common_codes
from app.db import master as master

__all__ = ["common_codes", "master"]
