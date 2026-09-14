import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio

from stevie.api import create_app
from stevie.devices import DeviceRegistry
from stevie.kernel import StevieKernel


@pytest_asyncio.fixture
async def api(tmp_path):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps({'version': 1, 'devices': [{
        'id': 'device-1', 'device_name': 'test_tv', 'display_name': 'Test TV',
        'ip_address': '192.0.2.10',
        'authentication': {'samsung': {'token': 'fake-secret-token'}},
        'targets': [{'target_id': 'target-1', 'name': 'samsung.remote.control',
                     'display_name': 'Remote'}],
    }]}))
    registry = DeviceRegistry(path)
    registry.load()
    kernel = StevieKernel()
    kernel.register(registry)
    kernel.register(SimpleNamespace(password='fake-secret-token'), name='configuration')
    app = create_app(kernel)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                                base_url='http://test') as client:
        yield client, kernel, registry, app


@pytest.mark.asyncio
async def test_health_and_shared_state(api):
    client, kernel, registry, app = api
    response = await client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'stevie'}
    assert app.state.kernel is kernel
    assert app.state.kernel.get('device_registry') is registry
    assert (await client.get('/health')).status_code == 404


@pytest.mark.asyncio
async def test_components_metadata_only(api):
    client, kernel, *_ = api
    response = await client.get('/api/v1/components')
    assert response.status_code == 200
    assert response.json() == {'components': [
        {'name': 'device_registry', 'type': 'DeviceRegistry'},
        {'name': 'configuration', 'type': 'SimpleNamespace'},
    ]}
    snapshot = kernel.components()
    snapshot.clear()
    assert len(kernel.components()) == 2
    assert 'fake-secret-token' not in response.text


@pytest.mark.asyncio
async def test_device_responses_are_safe(api):
    client, _, registry, _ = api
    listing = await client.get('/api/v1/devices')
    detail = await client.get('/api/v1/devices/device-1')
    assert listing.status_code == detail.status_code == 200
    assert listing.json() == {'devices': [detail.json()]}
    assert detail.json() == {
        'id': 'device-1', 'device_name': 'test_tv', 'display_name': 'Test TV',
        'ip_address': '192.0.2.10', 'targets': [{'target_id': 'target-1',
        'name': 'samsung.remote.control', 'display_name': 'Remote'}],
    }
    for forbidden in ('authentication', 'token', 'password', 'secret'):
        assert forbidden not in listing.text + detail.text
    assert registry.get('device-1').authentication['samsung']['token'] == 'fake-secret-token'
    registry.path.write_text('[]')
    registry.reload()
    assert (await client.get('/api/v1/devices')).json() == {'devices': []}


@pytest.mark.asyncio
async def test_missing_device(api):
    response = await api[0].get('/api/v1/devices/unknown')
    assert response.status_code == 404
    assert response.json() == {'detail': "Device 'unknown' was not found"}


@pytest.mark.asyncio
async def test_internal_failure_is_safe(api, monkeypatch):
    def broken():
        raise RuntimeError('fake-secret-token')
    monkeypatch.setattr(api[2], 'all', broken)
    response = await api[0].get('/api/v1/devices')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal server error'}


@pytest.mark.asyncio
async def test_openapi_and_docs(api):
    client = api[0]
    response = await client.get('/openapi.json')
    assert response.status_code == 200
    document = response.json()
    assert document['info']['title'] == 'Stevie API'
    assert set(document['paths']) == {'/api/v1/health', '/api/v1/components',
                                     '/api/v1/devices', '/api/v1/devices/{device_id}',
                                     '/api/v1/devices/{device_id}/commands'}
    assert set(document['paths']['/api/v1/devices/{device_id}/commands']) == {'get', 'post'}
    assert 'authentication' not in response.text
    assert (await client.get('/docs')).status_code == 200
    assert (await client.post('/api/v1/devices')).status_code == 405
