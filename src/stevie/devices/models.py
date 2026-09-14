"""The subset of Explorer device configuration understood by Core."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeviceTarget(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)

    target_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class Device(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)

    id: str = Field(min_length=1)
    device_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    ip_address: str = Field(min_length=1)
    targets: list[DeviceTarget] = Field(default_factory=list)
    authentication: dict[str, Any] | None = Field(
        default_factory=dict, repr=False, exclude=True,
    )

    @model_validator(mode="after")
    def unique_target_ids(self) -> Self:
        seen: set[str] = set()
        for target in self.targets:
            if target.target_id in seen:
                raise ValueError(f"Duplicate target ID: {target.target_id}")
            seen.add(target.target_id)
        return self
