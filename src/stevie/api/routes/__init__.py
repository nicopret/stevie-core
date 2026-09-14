from fastapi import APIRouter

from stevie.api.routes import components, devices, health, device_commands

router = APIRouter()
router.include_router(health.router)
router.include_router(components.router)
router.include_router(devices.router)
router.include_router(device_commands.router)
