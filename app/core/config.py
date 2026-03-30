"""Application settings and environment configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_NAME = "botfarm-service"
APP_VERSION = "0.1.0"
AUTH_USERNAME = "botfarm_admin"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
LOCK_TTL_SECONDS = 900
READINESS_DB_TIMEOUT_SECONDS = 2.0
RUN_MIGRATIONS_ON_STARTUP = False


class Settings(BaseSettings):
    """Runtime secrets and connection settings loaded from environment variables."""

    database_url: str = Field(alias="DATABASE_URL", min_length=1)
    botfarm_encryption_key: str = Field(alias="BOTFARM_ENCRYPTION_KEY", min_length=32)
    botfarm_encryption_fallback_keys: str = Field(
        default="",
        alias="BOTFARM_ENCRYPTION_FALLBACK_KEYS",
    )
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY", min_length=16)
    auth_password: str = Field(alias="AUTH_PASSWORD", min_length=8)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def encryption_fallback_keys(self) -> list[str]:
        """Return optional fallback Fernet keys used for key rotation."""
        raw = self.botfarm_encryption_fallback_keys.strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # type: ignore[call-arg]
