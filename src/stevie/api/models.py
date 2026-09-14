"""Public response schemas deliberately contain no authentication fields."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from stevie.devices.commands import CommandDefinition


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "stevie"


class ComponentResponse(BaseModel):
    name: str
    type: str


class ComponentListResponse(BaseModel):
    components: list[ComponentResponse]


class DeviceTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    name: str
    display_name: str


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    device_name: str
    display_name: str
    ip_address: str
    targets: list[DeviceTargetResponse]


class DeviceListResponse(BaseModel):
    devices: list[DeviceResponse]


class DeviceCommandRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={
        'examples': [{'command': 'remote.home'},
                     {'command': 'remote.key', 'arguments': {'key': 'KEY_GUIDE'}},
                     {'command': 'channel.select', 'arguments': {'channel': 101}}],
    })
    command: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class DeviceCommandResponse(BaseModel):
    device_id: str
    command: str
    status: Literal['completed'] = 'completed'
    result: None = None


class DeviceCommandCatalogueResponse(BaseModel):
    device_id: str
    commands: list[CommandDefinition]
