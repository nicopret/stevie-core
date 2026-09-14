import asyncio
import base64
import json
from pathlib import Path
from stevie.devices import Device, DeviceTarget
from unittest.mock import AsyncMock, Mock, call
from urllib.parse import parse_qs, urlsplit

import pytest

from stevie.devices.samsung import SamsungTVService
from stevie.eventbus import EventBus
from stevie.identifiers import ServiceName, TelemetryMessage, Topic
from stevie.kernel import StevieKernel


@pytest.fixture
def samsung(tmp_path, monkeypatch):
    kernel = StevieKernel()
    device = Device(id='device-tv-1', device_name='test_tv', display_name='Test TV',
                    ip_address='192.0.2.1',
                    targets=[DeviceTarget(target_id='target-1', name='samsung.remote.control', display_name='Remote')],
                    authentication={'samsung': {'token': 'fake-token'}})
    bus = EventBus()
    telemetry = Mock(emit=AsyncMock())
    kernel.register(bus)
    kernel.register(telemetry, name=ServiceName.TELEMETRY)
    service = SamsungTVService(kernel, device, app_name='Stevie test')
    ws = AsyncMock()
    ws.recv.return_value = json.dumps({'data': {}})
    connect = AsyncMock(return_value=ws)
    monkeypatch.setattr('stevie.devices.samsung.websockets.connect', connect)
    return service, device, bus, telemetry, ws, connect


@pytest.mark.asyncio
@pytest.mark.parametrize('authentication', [None, {}, {'samsung': None}, {'samsung': {}},
    {'samsung': {'token': ''}}, {'samsung': {'token': '  '}}, {'samsung': {'token': 123}}])
async def test_missing_authentication(samsung, authentication):
    service, device, _, _, _, connect = samsung
    device.authentication = authentication
    with pytest.raises(RuntimeError, match='pair the device through Stevie-Explorer'):
        await service.start()
    connect.assert_not_called()


def test_required_device_and_target(samsung):
    service, device, *_ = samsung
    with pytest.raises(TypeError):
        SamsungTVService(service.kernel)
    device.targets = []
    with pytest.raises(ValueError, match='requires target samsung.remote.control'):
        SamsungTVService(service.kernel, device)


@pytest.mark.asyncio
async def test_device_url_and_connection_lifecycle(samsung, tmp_path, caplog, capsys):
    service, device, bus, telemetry, ws, connect = samsung
    device.ip_address = '192.0.2.20'
    ws.recv.return_value = json.dumps({'data': {'token': 'fake-returned-token'}})
    connected, disconnected = AsyncMock(), AsyncMock()
    bus.subscribe(Topic.DEVICE_TV_CONNECTED, connected)
    bus.subscribe(Topic.DEVICE_TV_DISCONNECTED, disconnected)
    await service.start()
    await asyncio.gather(*tuple(bus._tasks))
    url = urlsplit(connect.await_args.args[0])
    assert url.netloc == '192.0.2.20:8002'
    assert url.path == '/api/v2/channels/samsung.remote.control'
    query = parse_qs(url.query)
    assert query['token'] == ['fake-token']
    assert base64.b64decode(query['name'][0]).decode() == 'Stevie test'
    ws.send.assert_not_called()
    await service.stop()
    await asyncio.gather(*tuple(bus._tasks))
    ws.close.assert_awaited_once_with()
    for callback in (connected, disconnected):
        callback.assert_awaited_once()
        event = callback.await_args.args[0]
        assert event.source == 'samsung_tv:device-tv-1'
        assert event.payload == {'device_id': device.id, 'display_name': device.display_name, 'ip': device.ip_address}
        assert 'fake-token' not in repr(event)
    assert device.authentication == {'samsung': {'token': 'fake-token'}}
    assert not list(tmp_path.rglob('*.token'))
    captured = capsys.readouterr()
    assert 'fake-token' not in captured.out + captured.err + caplog.text + repr(service)
    assert 'fake-token' not in repr(telemetry.emit.call_args_list)
    for emitted in telemetry.emit.call_args_list:
        assert emitted.kwargs['device_id'] == device.id


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', ['connect', 'greeting'])
async def test_connection_failure_is_safe(samsung, stage):
    service, _, _, telemetry, ws, connect = samsung
    error = OSError('URL contains fake-token')
    if stage == 'connect':
        connect.side_effect = error
    else:
        ws.recv.side_effect = error
    with pytest.raises(RuntimeError, match='Samsung connection failed') as caught:
        await service.start()
    assert 'fake-token' not in str(caught.value)
    assert 'fake-token' not in repr(telemetry.emit.call_args_list)
    assert telemetry.emit.await_args.args == (TelemetryMessage.SAMSUNG_CONNECTION_FAILED,)
    if stage == 'greeting':
        ws.close.assert_awaited_once()
        assert service._ws is None


def test_unique_stable_service_names(samsung):
    service, device, *_ = samsung
    other = device.model_copy(update={'id': 'device-tv-2'})
    second = SamsungTVService(service.kernel, other)
    service.kernel.register(service)
    service.kernel.register(second)
    assert service.kernel.get('samsung_tv:device-tv-1') is service
    assert service.kernel.get('samsung_tv:device-tv-2') is second


@pytest.mark.asyncio
async def test_remote_key_payload(samsung, monkeypatch):
    service, _, _, telemetry, ws, _ = samsung
    monkeypatch.setattr('stevie.devices.samsung.asyncio.sleep', AsyncMock())
    await service.start()
    await service.press('KEY_HOME')
    ws.send.assert_awaited_once()
    assert json.loads(ws.send.await_args.args[0]) == {
        'method': 'ms.remote.control',
        'params': {'Cmd': 'Click', 'DataOfCmd': 'KEY_HOME',
                   'Option': 'false', 'TypeOfRemote': 'SendRemoteKey'},
    }
    telemetry.emit.assert_awaited_with(
        TelemetryMessage.SAMSUNG_KEY_PRESS, source=service.name, key='KEY_HOME', **service._context(),
    )
    await service.stop()


@pytest.mark.asyncio
async def test_press_requires_connection(samsung):
    with pytest.raises(RuntimeError, match='Samsung TV is not connected'):
        await samsung[0].press('KEY_HOME')


@pytest.mark.asyncio
@pytest.mark.parametrize('method, key', [
    ('home', 'KEY_HOME'), ('mute', 'KEY_MUTE'),
    ('volume_up', 'KEY_VOLUP'), ('volume_down', 'KEY_VOLDOWN'),
])
async def test_convenience_keys(samsung, monkeypatch, method, key):
    service = samsung[0]
    press = AsyncMock()
    monkeypatch.setattr(service, 'press', press)
    await getattr(service, method)()
    press.assert_awaited_once_with(key)


@pytest.mark.asyncio
async def test_channel_digit_order(samsung, monkeypatch):
    service = samsung[0]
    press = AsyncMock()
    monkeypatch.setattr(service, 'press', press)
    monkeypatch.setattr('stevie.devices.samsung.asyncio.sleep', AsyncMock())
    await service.channel(123)
    assert press.await_args_list == [call('KEY_1'), call('KEY_2'), call('KEY_3'), call('KEY_ENTER')]


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['send', 'close'])
async def test_transport_errors_do_not_expose_credentials(samsung, operation):
    service, _, _, _, ws, _ = samsung
    await service.start()
    getattr(ws, operation).side_effect = OSError('fake-token')
    with pytest.raises(RuntimeError) as caught:
        if operation == 'send':
            await service.press('KEY_HOME')
        else:
            await service.stop()
    assert 'fake-token' not in str(caught.value)
