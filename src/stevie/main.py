import asyncio

from stevie.api.server import APIServerService
from stevie.config import Configuration
from stevie.devices import DeviceRegistry
from stevie.devices.commands import DeviceCommandService
from stevie.devices.samsung import SamsungTVService
from stevie.eventbus import EventBus
from stevie.kernel import StevieKernel
from stevie.telemetry import TelemetryService

async def main() -> None:
    kernel = StevieKernel()
    kernel.install_signal_handlers()

    config = Configuration()
    registry = DeviceRegistry(config.settings.devices_file)
    registry.load()
    eventbus = EventBus()
    telemetry = TelemetryService(eventbus)
    eventbus.set_telemetry(telemetry)

    kernel.register(config)
    kernel.register(registry)
    kernel.register(eventbus)
    kernel.register(telemetry)
    commands = DeviceCommandService(registry, eventbus, telemetry)
    kernel.register(commands)
    for device in registry.all():
        if any(target.name == SamsungTVService.target_name for target in device.targets):
            samsung = SamsungTVService(kernel, device)
            kernel.register(samsung)
            commands.register(device.id, samsung)

    kernel.register(APIServerService(kernel, config.settings.api_host, config.settings.api_port))

    await kernel.start()

    try:
        await kernel.wait_until_stopped()
    finally:
        await kernel.stop()


if __name__ == "__main__":
    asyncio.run(main())
