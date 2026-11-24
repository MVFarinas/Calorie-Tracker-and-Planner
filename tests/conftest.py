import pytest

from src.util.storage import DATA_FILE_ENV_VAR


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path_factory):
    """Point the home directory at a temp dir so no test can touch the real data file."""
    # A separate directory from tmp_path, so tests can assert on tmp_path's contents.
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() on Windows
    monkeypatch.delenv(DATA_FILE_ENV_VAR, raising=False)
    return home
