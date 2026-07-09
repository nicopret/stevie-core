import asyncio

from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.telemetry import TelemetryService


async def telemetry_listener(event: StevieEvent) -> None:
    print("Telemetry event received:")
    print("  topic:", event.topic)
    print("  source:", event.source)
    print("  payload:", event.payload)


async def main() -> None:
    eventbus = EventBus()
    telemetry = TelemetryService(eventbus)

    eventbus.set_telemetry(telemetry)
    eventbus.subscribe(Topic.SYSTEM_TELEMETRY_CREATED, telemetry_listener)

    await telemetry.start()

    await telemetry.emit(
        TelemetryMessage.SAMSUNG_CONNECTED,
        source=ServiceName.SAMSUNG_TV,
        ip="192.168.50.232",
    )

    await eventbus.publish_sync(
        StevieEvent(
            topic=Topic.DEVICE_TV_CONNECTED,
            source=ServiceName.SAMSUNG_TV,
            payload={"ip": "192.168.50.232"},
        )
    )


asyncio.run(main())
