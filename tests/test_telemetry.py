import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from stevie.eventbus import EventBus
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.telemetry import TelemetryService


@pytest.mark.asyncio
@pytest.mark.parametrize('message, method', [
    (TelemetryMessage.SAMSUNG_KEY_PRESS, 'debug'),
    (TelemetryMessage.SAMSUNG_CONNECTED, 'info'),
    (TelemetryMessage.SAMSUNG_CONNECTION_FAILED, 'error'),
])
async def test_emit_uses_definition_and_propagates_context(message, method):
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe(Topic.SYSTEM_TELEMETRY_CREATED, handler)
    telemetry = TelemetryService(bus)
    telemetry.log = Mock()
    await telemetry.emit(message, source=ServiceName.SAMSUNG_TV, key='KEY_HOME')
    await asyncio.gather(*tuple(bus._tasks))
    event = handler.await_args.args[0]
    definition = message.value
    assert event.topic == Topic.SYSTEM_TELEMETRY_CREATED
    assert event.source == ServiceName.TELEMETRY
    assert event.payload == {
        'key': definition.key,
        'grafana_key': definition.grafana_key,
        'level': definition.level.name,
        'category': definition.category.value,
        'description': definition.description,
        'source': str(ServiceName.SAMSUNG_TV),
        'context': {'key': 'KEY_HOME'},
    }
    assert len(telemetry.log.mock_calls) == 1
    getattr(telemetry.log, method).assert_called_once_with(
        definition.key, telemetry_key=definition.key,
        grafana_key=definition.grafana_key, telemetry_level=definition.level.name,
        category=definition.category.value, source=str(ServiceName.SAMSUNG_TV),
        description=definition.description, key='KEY_HOME',
    )
