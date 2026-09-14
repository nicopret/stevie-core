import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from stevie.api.server import APIServerService, KernelServer
from stevie.kernel import StevieKernel


@pytest.fixture
def server(monkeypatch):
    boundary = Mock(started=False, should_exit=False)

    async def serve():
        boundary.started = True
        while not boundary.should_exit:
            await asyncio.sleep(0)

    boundary.serve = AsyncMock(side_effect=serve)
    factory = Mock(return_value=boundary)
    monkeypatch.setattr('stevie.api.server.KernelServer', factory)
    kernel = StevieKernel()
    api = APIServerService(kernel, '127.0.0.1', 8123)
    kernel.register(api)
    return kernel, api, boundary, factory


@pytest.mark.asyncio
async def test_kernel_lifecycle(server):
    kernel, api, boundary, factory = server
    config = factory.call_args.args[0]
    assert (config.host, config.port) == ('127.0.0.1', 8123)
    assert config.app.state.kernel is kernel
    await kernel.start()
    boundary.serve.assert_awaited_once()
    task = api._task
    assert task is not None and not task.done()
    assert kernel.get('api_server') is api
    await kernel.stop()
    assert boundary.should_exit
    assert task.done()
    assert api._task is None
    await api.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [OSError('bind failed'), SystemExit(1), None])
async def test_startup_failure_rolls_back(server, error):
    kernel, api, boundary, _ = server
    previous = Mock(name='previous')
    previous.name = 'previous'
    previous.start = AsyncMock()
    previous.stop = AsyncMock()
    kernel = StevieKernel()
    kernel.register(previous)
    kernel.register(api)
    boundary.serve = AsyncMock(side_effect=error)
    with pytest.raises(RuntimeError, match='API server'):
        await kernel.start()
    previous.stop.assert_awaited_once()
    assert api._task is None
    assert not kernel.running


def test_signal_capture_does_not_install_handlers(monkeypatch):
    signal = Mock(side_effect=AssertionError('Uvicorn must not install signal handlers'))
    monkeypatch.setattr('signal.signal', signal)
    with KernelServer.capture_signals(None):
        pass
    signal.assert_not_called()


@pytest.mark.asyncio
async def test_unexpected_exit_requests_kernel_shutdown(server):
    kernel, api, boundary, _ = server
    finish = asyncio.Event()

    async def serve():
        boundary.started = True
        await finish.wait()
        raise OSError('server failed')

    boundary.serve.side_effect = serve
    await kernel.start()
    finish.set()
    await asyncio.wait_for(kernel.wait_until_stopped(), 1)
    await kernel.stop()
    assert api._task is None
