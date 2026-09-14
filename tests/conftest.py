import os
import socket
from unittest.mock import AsyncMock

import pytest

from stevie.config import StevieSettings


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    """Keep settings and filesystem writes independent of the developer's setup."""
    monkeypatch.chdir(tmp_path)
    for name in list(os.environ):
        if name.lower() in StevieSettings.model_fields:
            monkeypatch.delenv(name)

    def no_network(*args, **kwargs):
        raise AssertionError("Tests must not open network connections")

    monkeypatch.setattr(socket.socket, 'connect', no_network)
    monkeypatch.setattr(socket.socket, 'connect_ex', no_network)
    monkeypatch.setattr(
        'stevie.devices.samsung.websockets.connect',
        AsyncMock(side_effect=no_network),
    )
