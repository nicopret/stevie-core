import json
import unittest
from unittest.mock import call, patch

import pytest

from stevie.main import main
from stevie.devices import DeviceRegistry


@pytest.fixture(autouse=True)
def no_listener():
    with patch("stevie.main.APIServerService", autospec=True) as api:
        yield api



class MainTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_waits_for_shutdown_without_remote_commands(self) -> None:
        with (
            patch("stevie.main.StevieKernel", autospec=True) as kernel_class,
            patch("stevie.main.SamsungTVService", autospec=True) as samsung_class,
        ):
            kernel = kernel_class.return_value
            samsung = samsung_class.return_value
            kernel.get.return_value = samsung

            await main()

            kernel.install_signal_handlers.assert_called_once_with()
            samsung_class.assert_not_called()
            registries = [args.args[0] for args in kernel.register.call_args_list
                          if isinstance(args.args[0], DeviceRegistry)]
            self.assertEqual(len(registries), 1)
            self.assertEqual(registries[0].all(), [])
            kernel.start.assert_awaited_once_with()
            kernel.wait_until_stopped.assert_awaited_once_with()
            kernel.stop.assert_awaited_once_with()
            self.assertEqual(kernel.mock_calls[-3:], [
                call.start(), call.wait_until_stopped(), call.stop(),
            ])
            self.assertEqual(samsung.method_calls, [])


@pytest.mark.asyncio
async def test_main_loads_configured_registry(tmp_path, monkeypatch):
    path = tmp_path / 'configured.json'
    path.write_text(json.dumps([{
        'id': 'device-1', 'device_name': 'test_tv',
        'display_name': 'Test TV', 'ip_address': '192.0.2.10',
    }]))
    monkeypatch.setenv('DEVICES_FILE', str(path))
    with (
        patch('stevie.main.StevieKernel', autospec=True) as kernel_class,
        patch('stevie.main.SamsungTVService', autospec=True),
    ):
        await main()
        registry = next(args.args[0] for args in kernel_class.return_value.register.call_args_list
                        if isinstance(args.args[0], DeviceRegistry))
        assert registry.get('device-1').display_name == 'Test TV'


@pytest.mark.asyncio
async def test_main_creates_services_per_matching_device(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    from stevie.devices.samsung import SamsungTVService
    from stevie.kernel import StevieKernel

    records = [dict(id=f'device-{i}', device_name='same_model', display_name='Same label',
                    ip_address='192.0.2.10', authentication={'samsung': {'token': 'fake-token'}},
                    targets=[dict(target_id=f'target-{i}', name='samsung.remote.control', display_name='Remote')])
               for i in range(2)]
    records.append(dict(id='other', device_name='samsung_au8000', display_name='No remote',
                        ip_address='192.0.2.30'))
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps({'version': 1, 'devices': records}))
    original = path.read_bytes()
    monkeypatch.setenv('DEVICES_FILE', str(path))
    kernel = StevieKernel()
    with (
        patch('stevie.main.StevieKernel', return_value=kernel),
        patch.object(StevieKernel, 'install_signal_handlers'),
        patch.object(StevieKernel, 'wait_until_stopped', new_callable=AsyncMock),
        patch.object(SamsungTVService, 'start', new_callable=AsyncMock) as start,
        patch.object(SamsungTVService, 'stop', new_callable=AsyncMock),
    ):
        await main()
    assert start.await_count == 2
    registry = kernel.get('device_registry')
    for i in range(2):
        assert kernel.get(f'samsung_tv:device-{i}').device is registry.get(f'device-{i}')
        assert len(kernel.get('device_commands').catalogue(f'device-{i}')) == 9
    assert not kernel.has('samsung_tv:other')
    assert path.read_bytes() == original
    assert not (tmp_path / 'data' / 'samsung.token').exists()
