"""Transport-independent commands over explicitly registered runtime controllers."""

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel

from stevie.devices.registry import DeviceRegistry
from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.telemetry import TelemetryService


class Command(StrEnum):
    KEY = 'remote.key'
    HOME = 'remote.home'
    BACK = 'remote.back'
    VOLUME_UP = 'audio.volume_up'
    VOLUME_DOWN = 'audio.volume_down'
    MUTE = 'audio.mute'
    CHANNEL_UP = 'channel.up'
    CHANNEL_DOWN = 'channel.down'
    CHANNEL_SELECT = 'channel.select'


class CommandArgument(BaseModel):
    name: str
    type: str
    required: bool = True


class CommandDefinition(BaseModel):
    name: Command
    display_name: str
    arguments: list[CommandArgument]


class DeviceNotFoundError(Exception):
    pass


class DeviceControllerUnavailableError(Exception):
    pass


class UnknownCommandError(Exception):
    pass


class UnsupportedCommandError(Exception):
    pass


class InvalidCommandArgumentsError(Exception):
    pass


class DeviceTransportUnavailableError(RuntimeError):
    pass


class DeviceCommandExecutionError(Exception):
    pass


class DeviceCommandHandler(Protocol):
    @property
    def device_id(self) -> str: ...

    def command_catalogue(self) -> list[CommandDefinition]: ...

    async def execute_command(self, command: Command, arguments: dict[str, Any]) -> None: ...


class DeviceCommandService:
    name = ServiceName.DEVICE_COMMANDS

    def __init__(self, registry: DeviceRegistry, eventbus: EventBus, telemetry: TelemetryService):
        self.registry = registry
        self.eventbus = eventbus
        self.telemetry = telemetry
        self._controllers: dict[str, DeviceCommandHandler] = {}

    def register(self, device_id: str, controller: DeviceCommandHandler) -> None:
        self.registry.get(device_id)
        if controller.device_id != device_id:
            raise ValueError('Controller device identity does not match registration')
        if device_id in self._controllers:
            raise ValueError('A controller is already registered for this device')
        self._controllers[device_id] = controller

    def _controller(self, device_id: str) -> DeviceCommandHandler:
        if not self.registry.has(device_id):
            raise DeviceNotFoundError('Device was not found')
        if device_id not in self._controllers:
            raise DeviceControllerUnavailableError('Device controller is unavailable')
        return self._controllers[device_id]

    def catalogue(self, device_id: str) -> list[CommandDefinition]:
        return self._controller(device_id).command_catalogue()

    async def execute(self, device_id: str, command: str, arguments: dict[str, Any]) -> None:
        controller = self._controller(device_id)
        try:
            selected = Command(command)
        except ValueError:
            raise UnknownCommandError('Unknown command') from None
        if selected not in {item.name for item in controller.command_catalogue()}:
            raise UnsupportedCommandError('Command is not supported by this controller')
        context = {'device_id': device_id, 'command': selected.value}
        await self.telemetry.emit(TelemetryMessage.DEVICE_COMMAND_STARTED, source=self.name, **context)
        try:
            await controller.execute_command(selected, arguments)
        except (InvalidCommandArgumentsError, DeviceTransportUnavailableError):
            await self.telemetry.emit(TelemetryMessage.DEVICE_COMMAND_FAILED, source=self.name, **context)
            raise
        except Exception:
            await self.telemetry.emit(TelemetryMessage.DEVICE_COMMAND_FAILED, source=self.name, **context)
            raise DeviceCommandExecutionError('Device command failed') from None
        await self.eventbus.publish(StevieEvent(
            topic=Topic.DEVICE_COMMAND_COMPLETED, source=self.name, payload=context,
        ))
        await self.telemetry.emit(TelemetryMessage.DEVICE_COMMAND_COMPLETED, source=self.name, **context)
