from fastapi import APIRouter, HTTPException

from stevie.api.dependencies import RegistryDependency
from stevie.api.models import DeviceListResponse, DeviceResponse

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=DeviceListResponse)
async def devices(registry: RegistryDependency) -> DeviceListResponse:
    return DeviceListResponse(devices=[DeviceResponse.model_validate(device) for device in registry.all()])


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def device(device_id: str, registry: RegistryDependency) -> DeviceResponse:
    try:
        found = registry.get(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' was not found") from None
    return DeviceResponse.model_validate(found)
