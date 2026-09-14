import json

import pytest

from stevie.devices import DeviceRegistry
from stevie.identifiers import ServiceName
from stevie.kernel import Service, StevieKernel


@pytest.fixture
def records():
    return [
        {'id': 'device-1', 'device_name': 'test_tv', 'display_name': 'Test TV',
         'ip_address': '192.0.2.10',
         'targets': [{'target_id': 'target-1', 'name': 'samsung.remote.control',
                      'display_name': 'Samsung Remote Control'}],
         'authentication': {'samsung': {'token': 'fake-test-token'}}},
        {'id': 'device-2', 'device_name': 'test_tv', 'display_name': 'Other TV',
         'ip_address': '192.0.2.11'},
    ]


@pytest.mark.parametrize('wrapped', [False, True])
def test_load_and_query(tmp_path, records, wrapped, capsys, caplog):
    path = tmp_path / 'devices.json'
    document = {'version': 3, 'devices': records} if wrapped else records
    path.write_text(json.dumps(document))
    original = path.read_bytes()
    registry = DeviceRegistry(path)
    registry.load()
    assert [device.id for device in registry.all()] == ['device-1', 'device-2']
    assert registry.get('device-1').display_name == 'Test TV'
    assert registry.has('device-1')
    assert not registry.has('unknown')
    with pytest.raises(KeyError) as caught:
        registry.get('unknown')
    assert caught.value.args == ('unknown',)
    assert registry.find_by_name('test_tv') == registry.all()
    assert registry.find_by_name('absent') == []
    device = registry.get('device-1')
    assert device.targets[0].target_id == 'target-1'
    assert device.authentication['samsung']['token'] == 'fake-test-token'
    returned = registry.all()
    returned.clear()
    assert len(registry.all()) == 2
    assert path.read_bytes() == original
    captured = capsys.readouterr()
    assert 'fake-test-token' not in captured.out + captured.err + caplog.text


def test_missing_file_is_empty_and_not_created(tmp_path):
    path = tmp_path / 'absent' / 'devices.json'
    registry = DeviceRegistry(path)
    registry.load()
    assert registry.all() == []
    assert not path.parent.exists()


@pytest.mark.parametrize('document', [[], {'version': 0, 'devices': []}])
def test_empty_document(tmp_path, document):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(document))
    registry = DeviceRegistry(path)
    registry.load()
    assert registry.all() == []


@pytest.mark.parametrize('raw', ['', '{broken', '[{"authentication":"fake-test-token"}'])
def test_invalid_json_is_reported_without_contents(tmp_path, raw):
    path = tmp_path / 'devices.json'
    path.write_text(raw)
    with pytest.raises(ValueError, match='Invalid JSON') as caught:
        DeviceRegistry(path).load()
    assert 'fake-test-token' not in str(caught.value)


@pytest.mark.parametrize('document', [None, 12, {}, {'devices': {}},
    {'version': -1, 'devices': []}, [{'authentication': {'token': 'fake-test-token'}}]])
def test_invalid_schema_is_reported_safely(tmp_path, document, caplog, capsys):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='Invalid devices schema') as caught:
        DeviceRegistry(path).load()
    captured = capsys.readouterr()
    assert 'fake-test-token' not in str(caught.value) + caplog.text + captured.out + captured.err


def test_duplicate_devices_fail_atomically(tmp_path, records):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(records))
    registry = DeviceRegistry(path)
    registry.load()
    previous = registry.all()
    records[1]['id'] = records[0]['id']
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match='Duplicate device ID: device-1'):
        registry.load()
    assert registry.all() == previous


def test_duplicate_targets_fail_loading(tmp_path, records):
    records[0]['targets'] *= 2
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError, match='Invalid devices schema'):
        DeviceRegistry(path).load()


@pytest.mark.asyncio
async def test_registry_is_kernel_component(tmp_path):
    registry = DeviceRegistry(tmp_path / 'absent.json')
    registry.load()
    kernel = StevieKernel()
    kernel.register(registry)
    assert kernel.get(ServiceName.DEVICE_REGISTRY) is registry
    assert not isinstance(registry, Service)
    await kernel.start()
    assert kernel.running
    await kernel.stop()
    assert not kernel.running


def test_explorer_current_document_shape(tmp_path):
    # Matches Explorer's RegistryDocument/Target persistence, with synthetic data.
    record = {
        'id': '193a3333-85b9-59cc-8fac-a38c551040f7',
        'device_name': 'test_tv', 'display_name': 'Test TV', 'ip_address': '192.0.2.10',
        'authentication': None,
        'targets': [{'target_id': '42a6bf2e-9506-4665-bb74-3461879909f8',
                     'name': 'samsung.remote.control', 'display_name': 'Remote',
                     'device_id': '193a3333-85b9-59cc-8fac-a38c551040f7',
                     'transport': 'websocket', 'scheme': 'wss', 'port': 8002,
                     'path': '/api/v2/channels/samsung.remote.control',
                     'query': {}, 'headers': {}, 'tags': [],
                     'created_at': '2026-01-01T00:00:00Z'}],
    }
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps({'version': 2, 'devices': [record]}))
    registry = DeviceRegistry(path)
    registry.load()
    assert registry.get(record['id']).id == record['id']
    assert registry.get(record['id']).targets[0].target_id == record['targets'][0]['target_id']


def test_target_lookup(tmp_path, records):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(records))
    registry = DeviceRegistry(path)
    registry.load()
    assert registry.get_target('device-1', 'target-1') is registry.get('device-1').targets[0]
    for device_id, target_id, missing in [
        ('unknown', 'target-1', 'unknown'),
        ('device-1', 'unknown', 'unknown'),
        ('device-2', 'target-1', 'target-1'),
    ]:
        with pytest.raises(KeyError) as caught:
            registry.get_target(device_id, target_id)
        assert caught.value.args == (missing,)


def test_reload_explorer_changes(tmp_path, records, caplog, capsys):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps({'version': 1, 'devices': records}))
    registry = DeviceRegistry(path)
    registry.load()
    previous = registry.get('device-1')
    records[0]['ip_address'] = '192.0.2.20'
    records[0]['display_name'] = 'Updated TV'
    records[0]['targets'][0]['target_id'] = 'replacement-target'
    records[0]['targets'][0]['display_name'] = 'Updated Remote'
    records[1] = dict(id='device-3', device_name='test_media_device',
                      display_name='Test Media Device', ip_address='192.0.2.30', targets=[])
    path.write_text(json.dumps({'version': 2, 'devices': records}))
    contents = path.read_bytes()
    assert registry.get('device-1') is previous
    assert previous.ip_address == '192.0.2.10'
    registry.reload()
    device = registry.get('device-1')
    assert device.id == previous.id
    assert device.device_name == previous.device_name
    assert device.ip_address == '192.0.2.20'
    assert device.display_name == 'Updated TV'
    assert registry.get_target(device.id, 'replacement-target').display_name == 'Updated Remote'
    assert not registry.has('device-2')
    assert registry.get('device-3').device_name == 'test_media_device'
    assert device.authentication['samsung']['token'] == 'fake-test-token'
    assert path.read_bytes() == contents
    captured = capsys.readouterr()
    assert 'fake-test-token' not in captured.out + captured.err + caplog.text
    path.write_text(json.dumps({'version': 3, 'devices': []}))
    registry.reload()
    assert registry.all() == []


@pytest.mark.parametrize('failure', [
    'json', 'schema', 'duplicate_device', 'duplicate_target', 'missing', 'permission', 'utf8',
])
def test_failed_reload_preserves_state(tmp_path, records, monkeypatch, failure):
    path = tmp_path / 'devices.json'
    path.write_text(json.dumps(records))
    registry = DeviceRegistry(path)
    registry.load()
    previous = registry.all()
    expected = ValueError
    if failure == 'json':
        path.write_text('{broken')
    elif failure == 'schema':
        path.write_text(json.dumps([{'authentication': {'token': 'fake-test-token'}}]))
    elif failure == 'duplicate_device':
        records.append(records[0])
        path.write_text(json.dumps(records))
    elif failure == 'duplicate_target':
        records[0]['targets'] *= 2
        path.write_text(json.dumps(records))
    elif failure == 'missing':
        path.unlink()
        expected = FileNotFoundError
    elif failure == 'permission':
        def denied(*args, **kwargs):
            raise PermissionError('Access denied')
        monkeypatch.setattr(type(path), 'read_text', denied)
        expected = PermissionError
    else:
        path.write_bytes(b'\xff')
    with pytest.raises(expected) as caught:
        registry.reload()
    assert 'fake-test-token' not in str(caught.value)
    assert registry.all() == previous
    assert all(registry.get(device.id) is device for device in previous)
