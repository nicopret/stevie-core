import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import pytest_asyncio

from stevie.api import create_app
from stevie.devices import DeviceRegistry
from stevie.devices.commands import DeviceCommandService, DeviceTransportUnavailableError
from stevie.devices.samsung import SamsungTVService
from stevie.identifiers import TelemetryMessage, Topic
from stevie.kernel import StevieKernel, Service


@pytest_asyncio.fixture
async def setup(tmp_path):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps([dict(
        id=f'device-{i}', device_name='same_model', display_name='Same TV', ip_address='192.0.2.10',
        authentication={'samsung': {'token': 'fake-secret-token'}},
        targets=[dict(target_id=f'target-{i}', name='samsung.remote.control', display_name='Remote')],
    ) for i in range(3)]))
    registry = DeviceRegistry(path)
    registry.load()
    kernel = StevieKernel()
    kernel.register(registry)
    bus, telemetry = Mock(publish=AsyncMock()), Mock(emit=AsyncMock())
    commands = DeviceCommandService(registry, bus, telemetry)
    kernel.register(commands)
    controllers = []
    for i in range(2):
        controller = SamsungTVService(kernel, registry.get(f'device-{i}'))
        controller._ws = AsyncMock()
        for method in ['press', 'home', 'volume_up', 'volume_down', 'mute', 'channel']:
            setattr(controller, method, AsyncMock())
        commands.register(controller.device_id, controller)
        controllers.append(controller)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(kernel), raise_app_exceptions=False),
                                base_url='http://test') as client:
        yield client, commands, controllers, bus, telemetry


@pytest.mark.asyncio
@pytest.mark.parametrize('command,args,method,expected', [
    ('remote.key', {'key': 'KEY_GUIDE'}, 'press', ('KEY_GUIDE',)),
    ('remote.home', {}, 'home', ()), ('remote.back', {}, 'press', ('KEY_RETURN',)),
    ('audio.volume_up', {}, 'volume_up', ()), ('audio.volume_down', {}, 'volume_down', ()),
    ('audio.mute', {}, 'mute', ()), ('channel.up', {}, 'press', ('KEY_CHUP',)),
    ('channel.down', {}, 'press', ('KEY_CHDOWN',)),
    ('channel.select', {'channel': 123}, 'channel', (123,)),
])
async def test_dispatch_and_multi_device_routing(setup, command, args, method, expected):
    client, commands, controllers, bus, telemetry = setup
    assert not isinstance(commands, Service)
    response = await client.post('/api/v1/devices/device-1/commands', json={'command': command, 'arguments': args})
    assert response.status_code == 200
    assert response.json() == dict(device_id='device-1', command=command, status='completed', result=None)
    getattr(controllers[1], method).assert_awaited_once_with(*expected)
    for name in ['press', 'home', 'volume_up', 'volume_down', 'mute', 'channel']:
        getattr(controllers[0], name).assert_not_called()
    event = bus.publish.await_args.args[0]
    assert event.topic == Topic.DEVICE_COMMAND_COMPLETED
    assert event.payload == {'device_id': 'device-1', 'command': command}
    assert telemetry.emit.await_args.args == (TelemetryMessage.DEVICE_COMMAND_COMPLETED,)
    assert telemetry.emit.await_args.kwargs['device_id'] == 'device-1'
    assert 'fake-secret-token' not in repr(bus.mock_calls) + repr(telemetry.mock_calls) + response.text


@pytest.mark.asyncio
@pytest.mark.parametrize('command,args', [
    ('remote.key', {}), ('remote.key', {'key': ''}), ('remote.key', {'key': ' '}),
    ('remote.key', {'key': 1}), ('remote.key', {'key': 'KEY_POWER'}),
    ('remote.key', {'raw_payload': {'token': 'fake-secret-token'}}),
    ('remote.key', {'key': 'KEY_HOME', 'extra': True}),
    ('channel.select', {}), ('channel.select', {'channel': '123'}),
    ('channel.select', {'channel': True}), ('channel.select', {'channel': -1}),
    ('channel.select', {'channel': 1.5}), ('remote.home', {'unexpected': 'fake-secret-token'}),
])
async def test_invalid_arguments(setup, command, args):
    client, _, controllers, bus, _ = setup
    response = await client.post('/api/v1/devices/device-1/commands', json={'command': command, 'arguments': args})
    assert response.status_code == 422
    assert 'fake-secret-token' not in response.text
    bus.publish.assert_not_called()
    for name in ['press', 'home', 'channel']:
        getattr(controllers[1], name).assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [{}, {'command': ''}, {'command': 123},
    {'command': 'remote.home', 'arguments': 'fake-secret-token'},
    {'command': 'remote.home', 'token': 'fake-secret-token'}])
async def test_invalid_envelope(setup, body):
    response = await setup[0].post('/api/v1/devices/device-1/commands', json=body)
    assert response.status_code == 422
    assert 'fake-secret-token' not in response.text


@pytest.mark.asyncio
async def test_catalogue_is_local_and_safe(setup):
    client, _, controllers, *_ = setup
    controllers[1]._ws = None
    response = await client.get('/api/v1/devices/device-1/commands')
    assert response.status_code == 200
    definitions = response.json()['commands']
    assert len(definitions) == 9
    assert next(d for d in definitions if d['name'] == 'channel.select')['arguments'] == [
        {'name': 'channel', 'type': 'integer', 'required': True}]
    assert 'fake-secret-token' not in response.text
    assert 'verified' not in response.text
    controllers[1].press.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('device,status', [('missing', 404), ('device-2', 503)])
async def test_device_resolution_errors(setup, device, status):
    client = setup[0]
    assert (await client.get(f'/api/v1/devices/{device}/commands')).status_code == status
    assert (await client.post(f'/api/v1/devices/{device}/commands', json={'command': 'remote.home'})).status_code == status


@pytest.mark.asyncio
async def test_unknown_and_unsupported_are_distinct(setup):
    client, _, controllers, *_ = setup
    unknown = await client.post('/api/v1/devices/device-1/commands', json={'command': 'discover'})
    assert unknown.status_code == 400
    controllers[1].command_catalogue = lambda: []
    unsupported = await client.post('/api/v1/devices/device-1/commands', json={'command': 'remote.home'})
    assert unsupported.status_code == 422
    assert unknown.json()['detail'] != unsupported.json()['detail']


@pytest.mark.asyncio
@pytest.mark.parametrize('error,status', [(RuntimeError('fake-secret-token'), 500),
    (DeviceTransportUnavailableError('fake-secret-token'), 503)])
async def test_safe_execution_errors(setup, error, status):
    client, _, controllers, bus, telemetry = setup
    controllers[1].home.side_effect = error
    response = await client.post('/api/v1/devices/device-1/commands', json={'command': 'remote.home'})
    assert response.status_code == status
    assert 'fake-secret-token' not in response.text + repr(telemetry.mock_calls)
    bus.publish.assert_not_called()
    assert telemetry.emit.await_args.args == (TelemetryMessage.DEVICE_COMMAND_FAILED,)


@pytest.mark.asyncio
async def test_disconnected_controller(setup):
    setup[2][1]._ws = None
    response = await setup[0].post('/api/v1/devices/device-1/commands', json={'command': 'remote.home'})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_registration_rejects_conflicts(setup):
    _, commands, controllers, *_ = setup
    with pytest.raises(ValueError, match='already registered'):
        commands.register('device-1', controllers[1])
    with pytest.raises(ValueError, match='identity'):
        commands.register('device-2', controllers[1])
    with pytest.raises(KeyError):
        commands.register('missing', controllers[1])
