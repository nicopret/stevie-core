from stevie.config import Configuration, StevieSettings


def test_defaults():
    settings = Configuration().settings
    assert settings.stevie_env == 'development'
    assert settings.database_url == 'sqlite://data/stevie.db'
    assert settings.devices_file == 'data/devices.json'
    assert settings.api_host == '0.0.0.0'
    assert settings.api_port == 8000


def test_environment_overrides(monkeypatch, tmp_path):
    values = {
        'API_HOST': '127.0.0.1',
        'API_PORT': '8123',
        'STEVIE_ENV': 'test',
        'DATABASE_URL': 'sqlite://test.db',
        'DEVICES_FILE': str(tmp_path / 'devices.json'),
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = StevieSettings()
    for name, value in values.items():
        assert str(getattr(settings, name.lower())) == value
