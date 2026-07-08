import asyncio

from stevie.eventbus import EventBus
from stevie.events import StevieEvent

async def logger(event: StevieEvent) -> None:
    print("Logger:", event.topic, event.payload)

async def tv_handler(event: StevieEvent) -> None:
    print("TV Handler:", event.payload)

async def main():
    bus = EventBus()

    bus.subscribe("*", logger)

    bus.subscribe(
        "device.tv.*",
        tv_handler
    )

    await bus.publish_sync(
        StevieEvent(
            topic="device.tv.connected",
            source="living_room_tv",
            payload={
                "ip": "192.168.50.232"
            }
        )
    )

asyncio.run(main())
