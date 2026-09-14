from dataclasses import dataclass
from enum import Enum, IntEnum, StrEnum


class TelemetryLevel(IntEnum):
    TRACE = 10
    DEBUG = 20
    INFO = 30
    WARNING = 40
    ERROR = 50
    CRITICAL = 60


class TelemetryCategory(StrEnum):
    SYSTEM = "system"
    DEVICE = "device"
    PROVIDER = "provider"
    NETWORK = "network"
    DATABASE = "database"
    API = "api"


@dataclass(frozen=True, slots=True)
class TelemetryMessageDefinition:
    key: str
    level: TelemetryLevel
    category: TelemetryCategory
    grafana_key: str
    description: str


class TelemetryMessage(Enum):
    EVENTBUS_PUBLISH = TelemetryMessageDefinition(
        key="eventbus.publish",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.eventbus.publish",
        description="EventBus published an event.",
    )

    EVENTBUS_PUBLISH_SYNC = TelemetryMessageDefinition(
        key="eventbus.publish_sync",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.eventbus.publish_sync",
        description="EventBus synchronously published an event.",
    )

    EVENTBUS_HANDLER_FAILED = TelemetryMessageDefinition(
        key="eventbus.handler_failed",
        level=TelemetryLevel.ERROR,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.eventbus.handler_failed",
        description="EventBus handler failed.",
    )

    KERNEL_SERVICE_REGISTERED = TelemetryMessageDefinition(
        key="kernel.service_registered",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_registered",
        description="Kernel registered a component.",
    )

    KERNEL_STARTING = TelemetryMessageDefinition(
        key="kernel.starting",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.starting",
        description="Kernel is starting.",
    )

    KERNEL_STARTED = TelemetryMessageDefinition(
        key="kernel.started",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.started",
        description="Kernel started.",
    )

    KERNEL_STOPPING = TelemetryMessageDefinition(
        key="kernel.stopping",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.stopping",
        description="Kernel is stopping.",
    )

    KERNEL_STOPPED = TelemetryMessageDefinition(
        key="kernel.stopped",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.stopped",
        description="Kernel stopped.",
    )

    KERNEL_SERVICE_STARTING = TelemetryMessageDefinition(
        key="kernel.service_starting",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_starting",
        description="Kernel is starting a service.",
    )

    KERNEL_SERVICE_STARTED = TelemetryMessageDefinition(
        key="kernel.service_started",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_started",
        description="Kernel started a service.",
    )

    KERNEL_SERVICE_STOPPING = TelemetryMessageDefinition(
        key="kernel.service_stopping",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_stopping",
        description="Kernel is stopping a service.",
    )

    KERNEL_SERVICE_STOPPED = TelemetryMessageDefinition(
        key="kernel.service_stopped",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_stopped",
        description="Kernel stopped a service.",
    )

    KERNEL_START_FAILED = TelemetryMessageDefinition(
        key="kernel.start_failed",
        level=TelemetryLevel.ERROR,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.start_failed",
        description="Kernel failed to start.",
    )

    KERNEL_SERVICE_STOP_FAILED = TelemetryMessageDefinition(
        key="kernel.service_stop_failed",
        level=TelemetryLevel.ERROR,
        category=TelemetryCategory.SYSTEM,
        grafana_key="stevie.system.kernel.service_stop_failed",
        description="Kernel failed to stop a service cleanly.",
    )
    
    SAMSUNG_CONNECTING = TelemetryMessageDefinition(
        key="samsung.connecting",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.samsung.connecting",
        description="Connecting to Samsung TV.",
    )

    SAMSUNG_CONNECTED = TelemetryMessageDefinition(
        key="samsung.connected",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.samsung.connected",
        description="Samsung TV connected.",
    )

    SAMSUNG_CONNECTION_FAILED = TelemetryMessageDefinition(
        key="samsung.connection_failed",
        level=TelemetryLevel.ERROR,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.samsung.connection_failed",
        description="Samsung TV connection failed.",
    )

    SAMSUNG_KEY_PRESS = TelemetryMessageDefinition(
        key="samsung.key_press",
        level=TelemetryLevel.DEBUG,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.samsung.key_press",
        description="Samsung TV key press sent.",
    )

    DEVICE_COMMAND_STARTED = TelemetryMessageDefinition(
        key="device.command.started",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.command.started",
        description="Device command started.",
    )

    DEVICE_COMMAND_COMPLETED = TelemetryMessageDefinition(
        key="device.command.completed",
        level=TelemetryLevel.INFO,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.command.completed",
        description="Device command completed.",
    )

    DEVICE_COMMAND_FAILED = TelemetryMessageDefinition(
        key="device.command.failed",
        level=TelemetryLevel.ERROR,
        category=TelemetryCategory.DEVICE,
        grafana_key="stevie.device.command.failed",
        description="Device command failed.",
    )
