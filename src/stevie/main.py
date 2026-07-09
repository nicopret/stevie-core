import asyncio

from stevie.config import Configuration
from stevie.devices.samsung import SamsungTVService
from stevie.eventbus import EventBus
from stevie.kernel import StevieKernel
from stevie.telemetry import TelemetryService

async def main() -> None:
    kernel = StevieKernel()
    kernel.install_signal_handlers()

    config = Configuration()
    eventbus = EventBus()
    samsung = SamsungTVService(kernel)
    telemetry = TelemetryService(eventbus)
    eventbus.set_telemetry(telemetry)

    kernel.register(config)
    kernel.register(eventbus)
    kernel.register(telemetry)
    kernel.register(samsung)

    await kernel.start()

    await asyncio.sleep(2)

    await kernel.get("samsung_tv").volume_up()
    await asyncio.sleep(1)

    await kernel.get("samsung_tv").volume_down()
    await asyncio.sleep(1)

    await kernel.get("samsung_tv").mute()

    await kernel.wait_until_stopped()
    await kernel.stop()


if __name__ == "__main__":
    asyncio.run(main())
