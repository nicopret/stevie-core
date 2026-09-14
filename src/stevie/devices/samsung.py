from __future__ import annotations

import asyncio
import base64
import json
import ssl
from typing import Any

from stevie.devices.commands import Command, CommandDefinition, DeviceTransportUnavailableError
from stevie.devices.samsung_commands import catalogue, validate_arguments
from urllib.parse import urlencode

import websockets
from websockets.asyncio.client import ClientConnection

from stevie.devices.models import Device
from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.kernel import StevieKernel
from stevie.telemetry import TelemetryService


class SamsungTVService:
    target_name = "samsung.remote.control"

    def __init__(
        self,
        kernel: StevieKernel,
        device: Device,
        app_name: str = "Stevie",
    ) -> None:
        if not any(target.name == self.target_name for target in device.targets):
            raise ValueError(f"Device {device.id} requires target {self.target_name}")
        self.device = device
        self.name = f"{ServiceName.SAMSUNG_TV}:{device.id}"
        self.kernel = kernel
        self.app_name = app_name

        self.eventbus: EventBus | None = None
        self.telemetry: TelemetryService | None = None

        self._ws: ClientConnection | None = None

    @property
    def device_id(self) -> str:
        return self.device.id

    def command_catalogue(self) -> list[CommandDefinition]:
        return catalogue()

    async def execute_command(self, command: Command, arguments: dict[str, Any]) -> None:
        values = validate_arguments(command, arguments)
        if self._ws is None:
            raise DeviceTransportUnavailableError('Device transport is unavailable')
        if command == Command.KEY:
            await self.press(values['key'])
        elif command == Command.CHANNEL_SELECT:
            await self.channel(values['channel'])
        elif command in {Command.BACK, Command.CHANNEL_UP, Command.CHANNEL_DOWN}:
            await self.press({Command.BACK: 'KEY_RETURN', Command.CHANNEL_UP: 'KEY_CHUP',
                              Command.CHANNEL_DOWN: 'KEY_CHDOWN'}[command])
        else:
            await {Command.HOME: self.home, Command.VOLUME_UP: self.volume_up,
                   Command.VOLUME_DOWN: self.volume_down, Command.MUTE: self.mute}[command]()

    async def start(self) -> None:
        self.eventbus = self.kernel.get(ServiceName.EVENTBUS)
        self.telemetry = self.kernel.get(ServiceName.TELEMETRY)

        await self.telemetry.emit(
            TelemetryMessage.SAMSUNG_CONNECTING,
            source=self.name,
            **self._context(),
        )

        token = self._authentication_token()
        try:
            await self._connect(token)
        except Exception:
            await self.telemetry.emit(
                TelemetryMessage.SAMSUNG_CONNECTION_FAILED,
                source=self.name,
                **self._context(),
            )
            raise RuntimeError(
                f"Samsung connection failed for device {self.device.id}; "
                "check connectivity and authentication in Stevie-Explorer"
            ) from None

        await self.eventbus.publish(
            StevieEvent(
                topic=Topic.DEVICE_TV_CONNECTED,
                source=self.name,
                payload=self._context(),
            )
        )

        await self.telemetry.emit(
            TelemetryMessage.SAMSUNG_CONNECTED,
            source=self.name,
            **self._context(),
        )

    async def stop(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                raise RuntimeError(f"Samsung disconnect failed for device {self.device.id}") from None
            finally:
                self._ws = None

        if self.eventbus:
            await self.eventbus.publish(
                StevieEvent(
                    topic=Topic.DEVICE_TV_DISCONNECTED,
                    source=self.name,
                    payload=self._context(),
                )
            )

    async def press(self, key: str) -> None:
        if self._ws is None:
            raise RuntimeError("Samsung TV is not connected")

        if self.telemetry:
            await self.telemetry.emit(
                TelemetryMessage.SAMSUNG_KEY_PRESS,
                source=self.name,
                key=key,
                **self._context(),
            )

        payload = {
            "method": "ms.remote.control",
            "params": {
                "Cmd": "Click",
                "DataOfCmd": key,
                "Option": "false",
                "TypeOfRemote": "SendRemoteKey",
            },
        }

        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            raise DeviceTransportUnavailableError(f"Samsung key send failed for device {self.device.id}") from None
        await asyncio.sleep(0.5)

    async def home(self) -> None:
        await self.press("KEY_HOME")

    async def mute(self) -> None:
        await self.press("KEY_MUTE")

    async def volume_up(self) -> None:
        await self.press("KEY_VOLUP")

    async def volume_down(self) -> None:
        await self.press("KEY_VOLDOWN")

    async def channel(self, number: int) -> None:
        for digit in str(number):
            await self.press(f"KEY_{digit}")
            await asyncio.sleep(0.3)

        await self.press("KEY_ENTER")

    async def _connect(self, token: str) -> None:
        url = self._build_url(token)

        ssl_context = ssl._create_unverified_context()

        self._ws = await websockets.connect(
            url,
            ssl=ssl_context,
            ping_interval=None,
        )

        try:
            # Consume the greeting without persisting returned pairing credentials.
            await self._ws.recv()
        except BaseException:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            raise

    def _context(self) -> dict[str, str]:
        return {"device_id": self.device.id, "display_name": self.device.display_name,
                "ip": self.device.ip_address}

    def _authentication_token(self) -> str:
        samsung = (self.device.authentication or {}).get("samsung")
        token = samsung.get("token") if isinstance(samsung, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError(
                f"Samsung authentication unavailable for device {self.device.id}; "
                "pair the device through Stevie-Explorer"
            )
        return token

    def _build_url(self, token: str | None) -> str:
        encoded_name = base64.b64encode(
            self.app_name.encode("utf-8")
        ).decode("utf-8")

        params = {"name": encoded_name}

        if token:
            params["token"] = token

        host = self.device.ip_address
        if ":" in host:
            host = f"[{host}]"
        return (
            f"wss://{host}:8002/api/v2/channels/samsung.remote.control?"
            + urlencode(params)
        )
