import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from stevie.eventbus import EventBus
from stevie.events import StevieEvent
from stevie.identifiers import TelemetryMessage, Topic
from stevie.telemetry import TelemetryService


@pytest.mark.asyncio
@pytest.mark.parametrize('pattern, matches', [
    ('device.tv.connected', True), ('device.tv.disconnected', False),
    ('*', True), ('device.*', True), ('device.tv.*', True), ('system.*', False),
])
async def test_topic_matching(pattern, matches):
    bus = EventBus()
    handler = AsyncMock()
    bus.subscribe(pattern, handler)
    event = StevieEvent(Topic.DEVICE_TV_CONNECTED, 'test', {})
    await bus.publish_sync(event)
    if matches:
        handler.assert_awaited_once_with(event)
    else:
        handler.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_subscribers_and_unsubscribe():
    bus = EventBus()
    first, second = AsyncMock(), AsyncMock()
    bus.subscribe('*', first)
    bus.subscribe('device.*', second)
    event = StevieEvent(Topic.DEVICE_TV_CONNECTED, 'test', {})
    await bus.publish_sync(event)
    first.assert_awaited_once_with(event)
    second.assert_awaited_once_with(event)
    bus.unsubscribe('*', first)
    await bus.publish_sync(event)
    assert first.await_count == 1
    assert second.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('synchronous', [True, False])
async def test_publish_completion_semantics(synchronous):
    bus = EventBus()
    entered, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handler(event):
        entered.set()
        await release.wait()
        completed.set()

    bus.subscribe('*', handler)
    event = StevieEvent('device.tv.connected', 'test', {})
    publish = bus.publish_sync if synchronous else bus.publish
    task = asyncio.create_task(publish(event))
    try:
        async with asyncio.timeout(2):
            await entered.wait()
            assert not completed.is_set()
            if synchronous:
                assert not task.done()
            else:
                await task
            release.set()
            await completed.wait()
            await task
    finally:
        release.set()
        await asyncio.gather(task, *tuple(bus._tasks), return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize('background', [False, True])
@pytest.mark.parametrize('with_telemetry', [False, True])
async def test_handler_failure_isolation(background, with_telemetry):
    bus = EventBus()
    telemetry = Mock(emit=AsyncMock())
    if with_telemetry:
        bus.set_telemetry(telemetry)
    failing = AsyncMock(side_effect=RuntimeError('handler failed'))
    successful = AsyncMock()
    bus.subscribe('*', failing)
    bus.subscribe('*', successful)
    event = StevieEvent('device.tv.connected', 'test', {})
    if background:
        await bus.publish(event)
        await asyncio.gather(*tuple(bus._tasks))
    else:
        await bus.publish_sync(event)
    successful.assert_awaited_once_with(event)
    if with_telemetry:
        failure = telemetry.emit.await_args_list[-1]
        assert failure.args == (TelemetryMessage.EVENTBUS_HANDLER_FAILED,)
        assert failure.kwargs['error'] == 'handler failed'
        assert failure.kwargs['event_id'] == event.event_id
    else:
        telemetry.emit.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_publication_and_failure_do_not_recurse(monkeypatch):
    bus = EventBus()
    telemetry = TelemetryService(bus)
    telemetry.log = Mock()
    bus.set_telemetry(telemetry)
    original_emit = telemetry.emit
    emissions = []

    async def bounded_emit(message, **context):
        emissions.append(message)
        if len(emissions) > 1:
            raise AssertionError('Recursive telemetry emission')
        await original_emit(message, **context)

    monkeypatch.setattr(telemetry, 'emit', bounded_emit)
    received = AsyncMock()
    bus.subscribe(Topic.SYSTEM_TELEMETRY_CREATED, received)
    bus.subscribe(Topic.SYSTEM_TELEMETRY_CREATED, AsyncMock(side_effect=ValueError('failure')))
    await bus.publish_sync(StevieEvent('device.tv.connected', 'test', {}))
    await asyncio.gather(*tuple(bus._tasks))
    assert emissions == [TelemetryMessage.EVENTBUS_PUBLISH_SYNC]
    assert received.await_count == 1
