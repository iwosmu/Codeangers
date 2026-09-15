from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"


class Settings(BaseSettings):
    # OWNER E. Everything configurable lives here, nothing is read from os.environ elsewhere.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    gemini_api_key: str = ""
    mock_only: bool = True
    model_extract: str = "gemini-3.5-flash-lite"
    model_reason: str = "gemini-3.8-flash"
    cors_origins: str = "http://localhost:5173"
    commit: str = "dev"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
