"""Read-only device configuration lookup; Explorer owns persistence."""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from stevie.devices.models import Device, DeviceTarget
from stevie.identifiers import ServiceName


class _RegistryDocument(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    version: int = Field(default=0, ge=0)
    devices: list[Device]


class DeviceRegistry:
    name = ServiceName.DEVICE_REGISTRY

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._devices: dict[str, Device] = {}

    def load(self) -> None:
        """Validate the entire file before replacing the in-memory index."""
        self._load(missing_ok=True)

    def reload(self) -> None:
        """Read Explorer changes, retaining current state on any failure."""
        self._load(missing_ok=False)

    def _load(self, *, missing_ok: bool) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            if not missing_ok:
                raise
            self._devices = {}
            return
        except UnicodeError:
            raise ValueError(f"Invalid UTF-8 in devices file: {self.path}") from None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in devices file {self.path} "
                f"at line {exc.lineno}, column {exc.colno}"
            ) from None

        try:
            if isinstance(data, list):
                devices = TypeAdapter(list[Device]).validate_python(data)
            else:
                devices = _RegistryDocument.model_validate(data).devices
        except ValidationError as exc:
            # Validation inputs may contain credentials. Report only locations/types.
            details = "; ".join(
                f"{'.'.join(map(str, error['loc'])) or 'document'}: {error['type']}"
                for error in exc.errors(include_input=False, include_context=False)
            )
            raise ValueError(f"Invalid devices schema in {self.path}: {details}") from None

        incoming: dict[str, Device] = {}
        for device in devices:
            if device.id in incoming:
                raise ValueError(f"Duplicate device ID: {device.id}")
            incoming[device.id] = device
        self._devices = incoming

    def get(self, device_id: str) -> Device:
        return self._devices[device_id]

    def has(self, device_id: str) -> bool:
        return device_id in self._devices

    def get_target(self, device_id: str, target_id: str) -> DeviceTarget:
        """Look up a target within its owning device; unknown IDs raise KeyError."""
        for target in self.get(device_id).targets:
            if target.target_id == target_id:
                return target
        raise KeyError(target_id)

    def all(self) -> list[Device]:
        return list(self._devices.values())

    def find_by_name(self, device_name: str) -> list[Device]:
        return [device for device in self._devices.values() if device.device_name == device_name]
