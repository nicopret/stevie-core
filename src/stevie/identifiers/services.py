from enum import StrEnum

class ServiceName(StrEnum):
    CONFIGURATION = "configuration"
    DEVICE_REGISTRY = "device_registry"
    EVENTBUS = "eventbus"
    SAMSUNG_TV = "samsung_tv"
    TELEMETRY = "telemetry"
    API_SERVER = "api_server"
    DEVICE_COMMANDS = "device_commands"
