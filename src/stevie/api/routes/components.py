from fastapi import APIRouter

from stevie.api.dependencies import KernelDependency
from stevie.api.models import ComponentListResponse

router = APIRouter(tags=["components"])


@router.get("/components", response_model=ComponentListResponse)
async def components(kernel: KernelDependency) -> ComponentListResponse:
    return ComponentListResponse(components=kernel.components())
