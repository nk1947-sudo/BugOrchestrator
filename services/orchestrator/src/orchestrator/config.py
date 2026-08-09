from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_internal_url: str = Field(default="http://localhost:8000", alias="API_INTERNAL_URL")
    internal_service_token: str = Field(alias="INTERNAL_SERVICE_TOKEN")

    scan_worker_internal_url: str = Field(
        default="http://localhost:8090", alias="SCAN_WORKER_INTERNAL_URL"
    )

    poll_interval_seconds: int = Field(default=5, alias="ORCHESTRATOR_POLL_INTERVAL_SECONDS")
    max_concurrent_targets: int = Field(default=3, alias="ORCHESTRATOR_MAX_CONCURRENT_TARGETS")

    hitl_required_categories: str = Field(
        default="admin_access,destructive_state_change,aggressive_payload,waf_bypass",
        alias="HITL_REQUIRED_CATEGORIES",
    )
    hitl_approval_timeout_seconds: int = Field(default=3600, alias="HITL_APPROVAL_TIMEOUT_SECONDS")

    rate_limit_default_cooldown_seconds: int = Field(
        default=300, alias="RATE_LIMIT_DEFAULT_COOLDOWN_SECONDS"
    )

    shodan_api_key: str | None = Field(default=None, alias="SHODAN_API_KEY")
    censys_api_id: str | None = Field(default=None, alias="CENSYS_API_ID")
    censys_api_secret: str | None = Field(default=None, alias="CENSYS_API_SECRET")

    burp_api_base_url: str | None = Field(default=None, alias="BURP_API_BASE_URL")
    burp_api_key: str | None = Field(default=None, alias="BURP_API_KEY")

    findings_dir: str = Field(default="/workspace/findings", alias="FINDINGS_DIR")

    @property
    def hitl_categories(self) -> set[str]:
        return {c.strip() for c in self.hitl_required_categories.split(",") if c.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
