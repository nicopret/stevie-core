from __future__ import annotations

import logging
import structlog

from typing import Any

from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic

class TelemetryService:
    name = ServiceName.TELEMETRY

    def __init__(self, eventbus: EventBus | None = None) -> None:
        self.eventbus = eventbus
        self.log  = structlog.get_logger()
    
    async def start(self) -> None:
        self._configure_structlog()
    
    async def stop(self) -> None:
        pass
    
    async def emit(
        self,
        message: TelemetryMessage,
        source: str | ServiceName = ServiceName.TELEMETRY,
        **context: Any
    ) -> None:
        definition = message.value

        self._write_local(
            message=message,
            source=source,
            context=context
        )

        await self.eventbus.publish(
            StevieEvent(
                topic=Topic.SYSTEM_TELEMETRY_CREATED,
                source=ServiceName.TELEMETRY,
                payload={
                    "key": definition.key,
                    "grafana_key": definition.grafana_key,
                    "level": definition.level.name,
                    "category": definition.category.value,
                    "description": definition.description,
                    "source": str(source),
                    "context": context
                }
            )
        )
    
    def _write_local(
        self,
        message: TelemetryMessage,
        source: str | ServiceName,
        context: dict[str, Any],
    ) -> None:
        definition = message.value
        log_method = self._log_method(definition.level.name)

        log_method(
            definition.key,
            telemetry_key=definition.key,
            grafana_key=definition.grafana_key,
            telemetry_level=definition.level.name,
            category=definition.category.value,
            source=str(source),
            description=definition.description,
            **context
        )
    
    def _configure_structlog(self) -> None:
        logging.basicConfig(
            format="%(message)s",
            level=logging.INFO
        )

        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True
        )

    def _log_method(self, level: str):
        if level == "CRITICAL":
            return self.log.critical
        if level == "ERROR":
            return self.log.error
        if level == "WARNING":
            return self.log.warning
        if level == "DEBUG":
            return self.log.debug

        return self.log.info        