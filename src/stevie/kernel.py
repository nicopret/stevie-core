from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import structlog

log = structlog.get_logger()


@runtime_checkable
class Service(Protocol):
    name: str

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...


@dataclass
class StevieKernel:
    name: str = "stevie"
    running: bool = False

    _registry: dict[str, Any] = field(default_factory=dict)
    _services: list[Service] = field(default_factory=list)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    def register(self, component: Any, name: str | None = None) -> None:
        component_name = name or getattr(component, "name", component.__class__.__name__)

        if component_name in self._registry:
            raise ValueError(f"Component already registered: {component_name}")

        self._registry[component_name] = component

        if isinstance(component, Service):
            self._services.append(component)

        log.info(
            "kernel.component_registered",
            component=component_name,
            is_service=isinstance(component, Service),
        )

    def get(self, name: str) -> Any:
        return self._registry[name]

    def has(self, name: str) -> bool:
        return name in self._registry

    async def start(self) -> None:
        log.info("kernel.starting", name=self.name)

        started_services: list[Service] = []

        try:
            for service in self._services:
                log.info("kernel.service_starting", service=service.name)
                await service.start()
                started_services.append(service)
                log.info("kernel.service_started", service=service.name)

            self.running = True
            log.info("kernel.started", name=self.name)

        except Exception:
            log.exception("kernel.start_failed")

            for service in reversed(started_services):
                try:
                    await service.stop()
                except Exception:
                    log.exception("kernel.service_rollback_failed", service=service.name)

            raise

    async def stop(self) -> None:
        if not self.running:
            return

        log.info("kernel.stopping", name=self.name)

        for service in reversed(self._services):
            try:
                log.info("kernel.service_stopping", service=service.name)
                await service.stop()
                log.info("kernel.service_stopped", service=service.name)
            except Exception:
                log.exception("kernel.service_stop_failed", service=service.name)

        self.running = False
        self._stop_event.set()

        log.info("kernel.stopped", name=self.name)

    async def wait_until_stopped(self) -> None:
        await self._stop_event.wait()

    def request_stop(self) -> None:
        log.info("kernel.stop_requested", name=self.name)
        self._stop_event.set()

    def install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.request_stop)
