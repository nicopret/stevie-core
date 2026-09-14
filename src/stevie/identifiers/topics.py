from enum import StrEnum

class Topic(StrEnum):
    DEVICE_TV_CONNECTED = "device.tv.connected"
    DEVICE_TV_DISCONNECTED = "device.tv.disconnected"
    DEVICE_TV_MESSAGE = "device.tv.message"

    SYSTEM_TELEMETRY_CREATED = "system.telemetry.created"
    DEVICE_COMMAND_COMPLETED = "device.command.completed"
