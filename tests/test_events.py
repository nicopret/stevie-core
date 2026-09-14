from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from stevie.events import StevieEvent
from stevie.identifiers import ServiceName, Topic


def test_event_metadata_and_immutability():
    before = datetime.now(UTC)
    payload = {'ip': '192.0.2.1'}
    event = StevieEvent(Topic.DEVICE_TV_CONNECTED, ServiceName.SAMSUNG_TV, payload)
    other = StevieEvent(event.topic, event.source, {})
    assert event.topic == 'device.tv.connected'
    assert event.source == ServiceName.SAMSUNG_TV
    assert event.payload == payload
    assert UUID(event.event_id)
    assert event.event_id != other.event_id
    assert before <= event.timestamp <= datetime.now(UTC)
    assert event.timestamp.utcoffset() == timedelta(0)
    with pytest.raises(FrozenInstanceError):
        event.source = 'changed'


def test_identifiers_are_usable_as_strings():
    assert str(ServiceName.EVENTBUS) == 'eventbus'
    assert str(Topic.DEVICE_TV_CONNECTED) == 'device.tv.connected'
    assert {str(ServiceName.EVENTBUS): 'registered'}[ServiceName.EVENTBUS] == 'registered'
