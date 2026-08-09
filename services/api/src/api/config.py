from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration is read from environment variables (see .env.example).

    No default secret values are provided for anything security-sensitive -
    the service refuses to start rather than run with a guessable key.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    secret_key: str = Field(alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, alias="JWT_EXPIRE_MINUTES")

    database_url: str = Field(alias="DATABASE_URL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    dashboard_cors_origin: str = Field(
        default="http://localhost:3000", alias="DASHBOARD_CORS_ORIGIN"
    )

    admin_email: str = Field(default="admin@example.com", alias="ADMIN_EMAIL")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")

    internal_service_token: str = Field(alias="INTERNAL_SERVICE_TOKEN")

    hitl_required_categories: str = Field(
        default="admin_access,destructive_state_change,aggressive_payload,waf_bypass",
        alias="HITL_REQUIRED_CATEGORIES",
    )

    @property
    def hitl_categories(self) -> set[str]:
        return {c.strip() for c in self.hitl_required_categories.split(",") if c.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
