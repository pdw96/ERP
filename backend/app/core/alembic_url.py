"""Alembic 설정에 데이터베이스 URL 을 넣는 **한 자리.**

`migrations/env.py` 는 alembic 이 **파일 경로로 실행하는 스크립트**라 테스트가
불러들일 수 없다 — 불러들이는 순간 그 자리에서 마이그레이션이 돈다. 그래서
지켜야 하는 판단을 여기로 빼고 `env.py` 는 이것을 부르기만 한다. 테스트가
프로덕션과 **같은 코드**를 돌게 하는 것이 이 모듈의 유일한 이유다.

앞서 이 자리의 테스트는 이스케이프를 **자기가 다시 적어** 견주고 있었다. 그러면
프로덕션에서 이스케이프를 지워도 테스트는 초록으로 남는다 — 지키는 척만 하는
테스트다.
"""

from alembic.config import Config

from app.core import config as app_config


def escaped_for_configparser(url: str) -> str:
    """`%` 를 두 번 적는다.

    Alembic 설정은 configparser 이고 거기서 `%` 는 보간 구문이다. 비밀번호에
    `@` 가 하나만 있어도 URL 인코딩이 `%40` 을 만들고, 그대로 넣으면
    데이터베이스에 붙어 보기도 전에 터진다. 흔한 비밀번호 하나가 마이그레이션을
    통째로 막는 자리였다.
    """
    return url.replace("%", "%%")


def apply_database_url(config: Config) -> None:
    """**부르는 쪽이 URL 을 주면 그것이 이긴다.**

    설정으로 무조건 덮으면 테스트가 자기 DB 를 가리켜도 앱의 기본 DB 로 붙고,
    그 사고는 개발자의 로컬에 그 이름의 DB 가 있으면 **성공한 것처럼 보인다** —
    실제로 그렇게 지나갔고 CI 가 잡았다. 설정은 아무도 주지 않았을 때의
    기본값이지 우선값이 아니다.
    """
    if config.get_main_option("sqlalchemy.url", None):
        return

    config.set_main_option(
        "sqlalchemy.url", escaped_for_configparser(app_config.get_settings().database_url)
    )
