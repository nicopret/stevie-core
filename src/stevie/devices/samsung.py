from __future__ import annotations

import asyncio
import base64
import json
import ssl
from pathlib import Path
from urllib.parse import urlencode

import websockets
from websockets.asyncio.client import ClientConnection

from stevie.config import Configuration
from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.kernel import StevieKernel
from stevie.telemetry import TelemetryService


class SamsungTVService:
    name = ServiceName.SAMSUNG_TV

    def __init__(
        self,
        kernel: StevieKernel,
        app_name: str = "Stevie",
    ) -> None:
        self.kernel = kernel
        self.app_name = app_name

        self.ip: str | None = None
        self.token_file: Path | None = None

        self.eventbus: EventBus | None = None
        self.telemetry: TelemetryService | None = None

        self._ws: ClientConnection | None = None

    async def start(self) -> None:
        config: Configuration = self.kernel.get(ServiceName.CONFIGURATION)
        self.eventbus = self.kernel.get(ServiceName.EVENTBUS)
        self.telemetry = self.kernel.get(ServiceName.TELEMETRY)

        settings = config.settings

        if not settings.samsung_tv_ip:
            raise RuntimeError("SAMSUNG_TV_IP is required")

        self.ip = settings.samsung_tv_ip
        self.token_file = Path(settings.samsung_tv_token_file)

        await self.telemetry.emit(
            TelemetryMessage.SAMSUNG_CONNECTING,
            source=self.name,
            ip=self.ip,
        )

        try:
            await self._connect()
        except Exception:
            await self.telemetry.emit(
                TelemetryMessage.SAMSUNG_CONNECTION_FAILED,
                source=self.name,
                ip=self.ip,
            )
            raise

        await self.eventbus.publish(
            StevieEvent(
                topic=Topic.DEVICE_TV_CONNECTED,
                source=self.name,
                payload={"ip": self.ip},
            )
        )

        await self.telemetry.emit(
            TelemetryMessage.SAMSUNG_CONNECTED,
            source=self.name,
            ip=self.ip,
        )

    async def stop(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        if self.eventbus and self.ip:
            await self.eventbus.publish(
                StevieEvent(
                    topic=Topic.DEVICE_TV_DISCONNECTED,
                    source=self.name,
                    payload={"ip": self.ip},
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

        await self._ws.send(json.dumps(payload))
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

    async def _connect(self) -> None:
        token = self._load_token()
        url = self._build_url(token)

        ssl_context = ssl._create_unverified_context()

        self._ws = await websockets.connect(
            url,
            ssl=ssl_context,
            ping_interval=None,
        )

        first_message_raw = await self._ws.recv()
        first_message = json.loads(first_message_raw)

        new_token = first_message.get("data", {}).get("token")
        if new_token:
            self._save_token(new_token)

    def _build_url(self, token: str | None) -> str:
        if self.ip is None:
            raise RuntimeError("Samsung TV IP has not been configured")

        encoded_name = base64.b64encode(
            self.app_name.encode("utf-8")
        ).decode("utf-8")

        params = {"name": encoded_name}

        if token:
            params["token"] = token

        return (
            f"wss://{self.ip}:8002/api/v2/channels/samsung.remote.control?"
            + urlencode(params)
        )

    def _load_token(self) -> str | None:
        if self.token_file is None:
            raise RuntimeError("Samsung TV token file has not been configured")

        if not self.token_file.exists():
            return None

        token = self.token_file.read_text().strip()
        return token or None

    def _save_token(self, token: str) -> None:
        if self.token_file is None:
            raise RuntimeError("Samsung TV token file has not been configured")

        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(token)
