from typing import Annotated

from fastapi import Depends, Request

from stevie.devices import DeviceRegistry
from stevie.identifiers import ServiceName
from stevie.kernel import StevieKernel


async def get_kernel(request: Request) -> StevieKernel:
    return request.app.state.kernel


KernelDependency = Annotated[StevieKernel, Depends(get_kernel)]


async def get_registry(kernel: KernelDependency) -> DeviceRegistry:
    return kernel.get(ServiceName.DEVICE_REGISTRY)


RegistryDependency = Annotated[DeviceRegistry, Depends(get_registry)]
