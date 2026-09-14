from __future__ import annotations

import structlog

from pydantic_settings import BaseSettings, SettingsConfigDict
from stevie.identifiers import ServiceName

log = structlog.get_logger()

class StevieSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    stevie_env: str = "development"

    database_url: str = "sqlite://data/stevie.db"
    devices_file: str = "data/devices.json"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


class Configuration:
    name = ServiceName.CONFIGURATION

    def __init__(self) -> None:
        self.settings = StevieSettings()
        log.info(
            "configuration.loaded",
            environment=self.settings.stevie_env
        )
