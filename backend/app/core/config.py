"""환경에서 읽는 설정.

**시크릿을 코드에 쓰지 않는다.** 기본값은 로컬 Docker Compose 가 띄우는
개발용 데이터베이스를 가리키며, 그 값은 비밀이 아니다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """이 저장소가 환경에서 읽는 것 전부."""

    model_config = SettingsConfigDict(env_prefix="ERP_", env_file=".env", extra="ignore")

    # 로컬 compose 의 postgres 서비스를 가리킨다. 운영에서는 환경변수가 덮는다.
    database_url: str = "postgresql+psycopg://erp:erp@localhost:5432/erp"

    # 시드 판단 세 조건 중 둘째다 — 마이그레이션이 끝나 있고, 이 스위치가
    # 켜져 있고, 품목 표가 비어 있을 때만 시드한다. **운영에서 자동 시드는
    # 사고이지 편의가 아니므로** 기본값이 꺼짐이다.
    seed_enabled: bool = False


def get_settings() -> Settings:
    """설정 한 벌을 읽어 온다."""
    return Settings()
