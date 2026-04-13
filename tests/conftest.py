import pytest


@pytest.fixture
def tmp_role_home(tmp_path, monkeypatch):
    home = tmp_path / ".roleMe"
    home.mkdir()
    monkeypatch.setenv("ROLEME_HOME", str(home))
    return home
