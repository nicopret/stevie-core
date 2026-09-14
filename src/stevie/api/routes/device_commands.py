from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from stevie.api.dependencies import KernelDependency
from stevie.api.models import DeviceCommandRequest, DeviceCommandResponse, DeviceCommandCatalogueResponse
from stevie.devices.commands import (
    DeviceCommandService, DeviceNotFoundError, DeviceControllerUnavailableError,
    UnknownCommandError, UnsupportedCommandError, InvalidCommandArgumentsError,
    DeviceTransportUnavailableError, DeviceCommandExecutionError,
)
from stevie.identifiers import ServiceName

router = APIRouter(tags=['device commands'])


async def get_commands(kernel: KernelDependency) -> DeviceCommandService:
    return kernel.get(ServiceName.DEVICE_COMMANDS)


CommandsDependency = Annotated[DeviceCommandService, Depends(get_commands)]
ERRORS = {
    DeviceNotFoundError: (404, 'Device was not found'),
    DeviceControllerUnavailableError: (503, 'Device controller is unavailable'),
    UnknownCommandError: (400, 'Unknown command'),
    UnsupportedCommandError: (422, 'Command is not supported by this controller'),
    InvalidCommandArgumentsError: (422, 'Invalid command arguments'),
    DeviceTransportUnavailableError: (503, 'Device transport is unavailable'),
    DeviceCommandExecutionError: (500, 'Device command failed'),
}


def http_error(error: Exception) -> HTTPException:
    status, detail = ERRORS[type(error)]
    return HTTPException(status_code=status, detail=detail)


@router.get('/devices/{device_id}/commands', response_model=DeviceCommandCatalogueResponse)
async def catalogue(device_id: str, commands: CommandsDependency) -> DeviceCommandCatalogueResponse:
    try:
        definitions = commands.catalogue(device_id)
    except tuple(ERRORS) as error:
        raise http_error(error) from None
    return DeviceCommandCatalogueResponse(device_id=device_id, commands=definitions)


@router.post('/devices/{device_id}/commands', response_model=DeviceCommandResponse)
async def execute(device_id: str, request: DeviceCommandRequest,
                  commands: CommandsDependency) -> DeviceCommandResponse:
    try:
        await commands.execute(device_id, request.command, request.arguments)
    except tuple(ERRORS) as error:
        raise http_error(error) from None
    return DeviceCommandResponse(device_id=device_id, command=request.command)
