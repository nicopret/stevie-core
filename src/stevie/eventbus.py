from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any

import structlog

from stevie.events import StevieEvent

log = structlog.get_logger()

EventHandler = Callable[[Any], Awaitable[None]]

@dataclass(frozen=True, slots=True)
class Subscription:
    topic_pattern: str
    handler: EventHandler

class EventBus:
    def __init__(self):
        self._subscriptions: list[Subscription] = []
        self._tasks: set[asycnio.Task[None]] = set()
    
    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        self._subscriptions.append(
            Subscription(topic_pattern=topic_pattern, handler=handler)
        )

        log.info(
            "eventbus.subscribed",
            topic_pattern=topic_pattern,
            handler=getattr(handler, "__name__", repr(handler))
        )
    
    def unsubscribed(self, topic_pattern: str, handler: EventHandler) -> None:
        self._subscriptions = [
            sub
            for sub in self._subscriptions
            if not (
                sub.topic_pattern == topic_pattern
                and sub.handler == handler
            )
        ]

        log.info(
            "eventbus.unsubscribed",
            topic_pattern=topic_pattern,
            handler=getattr(handler, "__name__", repr(handler))
        )

    async def publish(self, event:Any) -> None:
        """
        Fire-and-forget publish

        Handlers run in background tasks
        """
        handlers = self._matching_handlers(event.topic)

        log.info(
            "eventbus.publish",
            topic=event.topic,
            source=event.source,
            event_id=event.event_id,
            handlers=len(handlers)
        )

        for handler in handlers:
            task = asycnio.create_task(
                self._run_handler(handler, event)
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
    
    async def publish_sync(self, event: StevieEvent) -> None:
        """
        Publish and wait for all handlers to finish
        """
        handlers = self._matching_handlers(event.topic)

        log.info(
            "eventbus.publish_sync",
            topic=event.topic,
            source=event.source,
            event_id=event.event_id,
            handlers=len(handlers)
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
        event: StevieEvent
    ) -> None:
        try:
            await handler(event)
        except Exception:
            log.excetption(
                "eventbus.handler_failed",
                topic=event.topic,
                source=event.source,
                event_id=event.event_id,
                handler=getattr(handler, "__name__", repr(handler))
            )
