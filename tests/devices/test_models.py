import pytest
from pydantic import ValidationError

from stevie.devices import Device, DeviceTarget


def minimal_device(**overrides):
    return dict(id='device-1', device_name='test_tv', display_name='Test TV',
                ip_address='192.0.2.10', **overrides)


def test_minimum_device_and_independent_defaults():
    first = Device.model_validate(minimal_device())
    second = Device.model_validate(minimal_device())
    assert first.id == 'device-1'
    assert first.targets == []
    assert first.authentication == {}
    first.targets.append(DeviceTarget(target_id='target-1', name='remote', display_name='Remote'))
    first.authentication['vendor'] = {'token': 'fake-test-token'}
    assert second.targets == []
    assert second.authentication == {}


def test_target_and_authentication_preserved_but_not_exposed():
    target = {'target_id': 'target-1', 'name': 'samsung.remote.control',
              'display_name': 'Samsung Remote Control', 'transport': 'websocket',
              'headers': {'Authorization': 'fake-header'}}
    device = Device.model_validate(minimal_device(
        targets=[target], authentication={'vendor': {'token': 'fake-test-token'}},
    ))
    assert device.targets[0].target_id == 'target-1'
    assert device.targets[0].name == 'samsung.remote.control'
    assert device.targets[0].display_name == 'Samsung Remote Control'
    assert device.authentication['vendor']['token'] == 'fake-test-token'
    for rendered in (repr(device), str(device), device.model_dump_json(), str(device.model_dump())):
        assert 'fake-test-token' not in rendered
        assert 'fake-header' not in rendered
    assert 'authentication' not in device.model_dump()


def test_explorer_nullable_authentication():
    assert Device.model_validate(minimal_device(authentication=None)).authentication is None


@pytest.mark.parametrize('field', ['id', 'device_name', 'display_name', 'ip_address'])
@pytest.mark.parametrize('invalid', [None, '', 123, ['invalid']])
def test_invalid_required_fields(field, invalid):
    record = minimal_device()
    record[field] = invalid
    with pytest.raises(ValidationError):
        Device.model_validate(record)


@pytest.mark.parametrize('field', ['id', 'device_name', 'display_name', 'ip_address'])
def test_required_fields_are_not_generated(field):
    record = minimal_device()
    del record[field]
    with pytest.raises(ValidationError):
        Device.model_validate(record)


def test_duplicate_target_ids_rejected():
    target = dict(target_id='target-1', name='remote', display_name='Remote')
    with pytest.raises(ValidationError, match='Duplicate target ID: target-1'):
        Device.model_validate(minimal_device(targets=[target, target]))
