from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from stevie.identifiers import ServiceName, TelemetryMessage

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
        component_name = str(
            name or getattr(component, "name", component.__class__.__name__)
        )

        if component_name in self._registry:
            raise ValueError(f"Component already registered: {component_name}")

        self._registry[component_name] = component

        if isinstance(component, Service):
            self._services.append(component)

    def get(self, name: str | ServiceName) -> Any:
        return self._registry[str(name)]

    def has(self, name: str | ServiceName) -> bool:
        return str(name) in self._registry

    def components(self) -> list[dict[str, str]]:
        """Return a detached metadata snapshot, never component state."""
        return [{"name": name, "type": type(component).__name__}
                for name, component in self._registry.items()]

    async def start(self) -> None:
        await self._emit(
            TelemetryMessage.KERNEL_STARTING,
            name=self.name
        )

        started_services: list[Service] = []

        try:
            for service in self._services:
                await self._emit(
                    TelemetryMessage.KERNEL_SERVICE_STARTING,
                    service=str(service.name)
                )
                await service.start()
                started_services.append(service)

                await self._emit(
                    TelemetryMessage.KERNEL_SERVICE_STARTED,
                    service=str(service.name)
                )

            self.running = True
            await self._emit(
                TelemetryMessage.KERNEL_STARTED,
                name=self.name
            )

        except Exception as exc:
            await self._emit(
                TelemetryMessage.KERNEL_START_FAILED,
                name=self.name,
                error=str(exc)
            )

            for service in reversed(started_services):
                try:
                    await service.stop()
                except Exception:
                    pass

            raise

    async def stop(self) -> None:
        if not self.running:
            return

        await self._emit(
            TelemetryMessage.KERNEL_STOPPING,
            name=self.name
        )

        for service in reversed(self._services):
            try:
                await self._emit(
                    TelemetryMessage.KERNEL_SERVICE_STOPPING,
                    service=str(service.name)
                )
                await service.stop()
                await self._emit(
                    TelemetryMessage.KERNEL_SERVICE_STOPPED,
                    service=str(service.name)
                )
            except Exception as exc:
                await self._emit(
                    TelemetryMessage.KERNEL_SERVICE_STOP_FAILED,
                    service=str(service.name),
                    error=str(exc)
                )

        self.running = False
        self._stop_event.set()

        await self._emit(
            TelemetryMessage.KERNEL_STOPPED,
            name=self.name
        )

    async def wait_until_stopped(self) -> None:
        await self._stop_event.wait()

    def request_stop(self) -> None:
        self._stop_event.set()

    def install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self.request_stop)

    async def _emit(
        self,
        message: TelemetryMessage,
        **context
    ) -> None:
        if not self.has(ServiceName.TELEMETRY):
            return
        
        telemetry = self.get(ServiceName.TELEMETRY)

        await telemetry.emit(
            message,
            source="kernel",
            **context
        )
