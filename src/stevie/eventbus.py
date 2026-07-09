from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import TYPE_CHECKING

from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic

if TYPE_CHECKING:
    from stevie.telemetry import TelemetryService


EventHandler = Callable[[StevieEvent], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Subscription:
    topic_pattern: str
    handler: EventHandler


class EventBus:
    name = ServiceName.EVENTBUS

    def __init__(self) -> None:
        self._subscriptions: list[Subscription] = []
        self._tasks: set[asyncio.Task[None]] = set()
        self.telemetry: TelemetryService | None = None

    def set_telemetry(self, telemetry: TelemetryService) -> None:
        self.telemetry = telemetry

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        self._subscriptions.append(
            Subscription(
                topic_pattern=str(topic_pattern),
                handler=handler,
            )
        )

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        self._subscriptions = [
            sub
            for sub in self._subscriptions
            if not (
                sub.topic_pattern == str(topic_pattern)
                and sub.handler == handler
            )
        ]

    async def publish(self, event: StevieEvent) -> None:
        handlers = self._matching_handlers(str(event.topic))

        await self._emit_telemetry(
            TelemetryMessage.EVENTBUS_PUBLISH,
            topic=str(event.topic),
            origin=str(event.source),
            event_id=event.event_id,
            handlers=len(handlers),
        )

        for handler in handlers:
            task = asyncio.create_task(
                self._run_handler(handler, event)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def publish_sync(self, event: StevieEvent) -> None:
        handlers = self._matching_handlers(str(event.topic))

        await self._emit_telemetry(
            TelemetryMessage.EVENTBUS_PUBLISH_SYNC,
            topic=str(event.topic),
            origin=str(event.source),
            event_id=event.event_id,
            handlers=len(handlers),
        )

        await asyncio.gather(
            *(self._run_handler(handler, event) for handler in handlers)
        )

    def _matching_handlers(self, topic: str) -> list[EventHandler]:
        return [
            sub.handler
            for sub in self._subscriptions
            if self._topic_matches(sub.topic_pattern, topic)
        ]

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        if pattern == "*":
            return True

        return fnmatch(topic, pattern)

    async def _run_handler(
        self,
        handler: EventHandler,
        event: StevieEvent,
    ) -> None:
        try:
            await handler(event)

        except Exception as exc:
            await self._emit_telemetry(
                TelemetryMessage.EVENTBUS_HANDLER_FAILED,
                topic=str(event.topic),
                origin=str(event.source),
                event_id=event.event_id,
                handler=getattr(handler, "__name__", repr(handler)),
                error=str(exc),
            )

    async def _emit_telemetry(
        self,
        message: TelemetryMessage,
        **context,
    ) -> None:
        if self.telemetry is None:
            return

        if context.get("topic") == str(Topic.SYSTEM_TELEMETRY_CREATED):
            return

        await self.telemetry.emit(
            message,
            source=ServiceName.EVENTBUS,
            **context,
        )
