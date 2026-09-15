"""마이그레이션 파이프가 도는가.

**표가 아직 없어도 이 테스트는 값이 있다.** 「스키마 변경에 마이그레이션이
있다」를 지키려면 마이그레이션이 실제로 도는 길이 처음부터 서 있어야 하고,
첫 표를 만들 때 이 길이 막혀 있으면 재시드가 유일한 수단이 된다.

다만 가설공사가 책임지는 것은 **파이프가 뚫려 있는가**까지다. 모델과
마이그레이션이 같은 표를 만드는지, 되돌리는 길이 실제로 도는지는 첫 표가
서는 본 공사의 일이며, 그때 이 파일이 강화되어야 한다 — 아래 마지막 테스트가
그 시점에 실패해서 알려 준다.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config("postgresql+psycopg://x/y"))


def test_the_migration_history_is_a_single_line() -> None:
    """머리가 둘이면 어느 쪽이 진실인지 아무도 모른다."""
    heads = _script_directory().get_heads()

    assert len(heads) <= 1, f"마이그레이션 머리가 둘 이상이다: {heads}"


def test_the_url_is_not_written_in_alembic_ini() -> None:
    """URL 을 `alembic.ini` 에 적지 않는다 — 두 벌이면 반드시 갈린다.

    `env.py` 가 설정에서 읽으므로 ini 에 적으면 같은 값이 두 곳에 산다.
    """
    config = Config(str(BACKEND_ROOT / "alembic.ini"))

    assert config.get_main_option("sqlalchemy.url", None) in (None, "")


def test_alembic_connects_to_the_url_it_is_given(engine: Engine) -> None:
    """**부르는 쪽이 준 URL 이 이긴다.** 설정은 기본값이지 우선값이 아니다.

    이 테스트가 CI 에서 처음 터졌다. `env.py` 가 준 URL 을 설정값으로 덮어써
    앱의 기본 DB 로 붙고 있었는데, 개발자의 로컬에 그 이름의 DB 가 있어서
    **잘못된 DB 에 붙고도 성공했다.** `conftest` 의 가드가 이제 그 함정을
    로컬에서도 드러낸다 — 앱 기본 URL 은 닿을 수 없는 값으로 덮여 있으므로,
    이 테스트가 그리로 붙으면 곧바로 터진다.

    오류 없이 끝나는 것 자체가 확인이다. 리비전이 없으므로 아무 표도 만들지
    않는다.
    """
    command.upgrade(_alembic_config(engine.url.render_as_string(hide_password=False)), "head")


def test_the_first_revision_has_not_landed_yet() -> None:
    """첫 리비전이 서는 순간 이 파일을 강화하라는 표식.

    지금은 리비전이 0개라 위 테스트가 「명령이 돈다」까지만 본다. 첫 표가
    서면 확인해야 할 것이 둘 늘어난다 — **마이그레이션이 모델과 같은 표를
    만드는가**(자료형 · 널 허용 · 기본키 · 외래키 · 유일키 · CHECK)와
    **한 엔진의 방언이 마이그레이션에 굽히지 않았는가**.

    미룬다는 사실 자체를 코드가 알고 있게 한다. 이 테스트가 실패하면 그것은
    고장이 아니라 **다음 할 일의 알림**이다.
    """
    revisions = list(_script_directory().walk_revisions())

    assert revisions == [], (
        f"첫 리비전 {len(revisions)}개가 섰다 — 이 파일을 왕복 검증으로 바꿔라.\n"
        "  ① 마이그레이션이 모델과 같은 표를 만드는지 견주는 테스트\n"
        "  ② 마이그레이션에 한 엔진의 방언이 문자열로 박히지 않았는지 보는 테스트\n"
        "  그리고 이 테스트를 지운다."
    )
