from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

class StevieSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    stevie_env: str = "development"

    database_url: str = "sqlite://data/stevie.db"

    samsung_tv_ip: str | None = None
    samsung_tv_token_file: str = "data/samsung.token"

class ConfigurationService:
    name = "configuration"

    def __init__(self) -> None:
        self.settings: StevieSettings | None = None
    
    async def start(self) -> None:
        self.settings = StevieSettings()

    async def stop(self) -> None:
        pass
