import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path

import pytest

from src.entry import CaloriesLog, DailyEntry
from src.util import storage
from src.util.file_loader import FileLoader
from src.util.storage import (
    DATA_FILE_ENV_VAR,
    StorageError,
    default_data_file,
    format_date,
    load_log,
    resolve_data_file,
    save_log,
)

ROWS = [(1, 200.0, 2200), (2, 199.4, 2100), (5, 198.6, 2000)]


def make_log(rows=ROWS):
    log = CaloriesLog()
    for day, weight, calories in rows:
        assert log.add_entry(DailyEntry(datetime(2025, 7, day), weight, calories))
    return log


def signature(entries):
    return [(e.date.strftime("%Y-%m-%d"), float(e.weight), e.calories) for e in entries]


# --- Round trip -------------------------------------------------------------

def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "log.json"
    log = make_log()
    save_log(log, path)
    assert signature(load_log(path)) == signature(log)


def test_saved_file_uses_import_schema(tmp_path):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    data = json.loads(path.read_text())
    assert data[0] == {"date": "2025-07-01", "weight": 200.0, "calories": 2200}
    # ... so the JSON importer reads it too.
    assert signature(FileLoader.load_file(str(path))) == signature(make_log())


def test_empty_log_round_trips(tmp_path):
    path = tmp_path / "log.json"
    save_log(CaloriesLog(), path)
    assert json.loads(path.read_text()) == []
    assert len(load_log(path)) == 0


def test_early_years_are_zero_padded(tmp_path):
    # strftime("%Y") gives "225" for year 225 on glibc, which the loader rejects.
    assert format_date(datetime(225, 1, 1)) == "0225-01-01"
    path = tmp_path / "log.json"
    log = CaloriesLog()
    assert log.add_entry(DailyEntry(datetime(225, 1, 1), 200.0, 2200))
    save_log(log, path)
    assert json.loads(path.read_text())[0]["date"] == "0225-01-01"
    assert signature(load_log(path)) == signature(log)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need extra privileges on Windows")
def test_save_through_symlink_updates_target(tmp_path):
    target = tmp_path / "real.json"
    target.write_text("[]")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    save_log(make_log(), link)
    assert link.is_symlink()
    assert signature(load_log(target)) == signature(make_log())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["link.json", "real.json"]


def test_save_creates_missing_directories(tmp_path):
    path = tmp_path / "a" / "b" / "log.json"
    save_log(make_log(), path)
    assert len(load_log(path)) == 3


def test_save_overwrites_previous_contents(tmp_path):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    save_log(make_log(ROWS[:1]), path)
    assert len(load_log(path)) == 1


# --- Atomic writes and permissions -------------------------------------------

def test_save_leaves_no_temp_files(tmp_path):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    save_log(make_log(), path)
    assert [p.name for p in tmp_path.iterdir()] == ["log.json"]


def test_failed_save_keeps_old_file_and_removes_temp(tmp_path, monkeypatch):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    before = path.read_bytes()

    def interrupted_dump(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(storage.json, "dump", interrupted_dump)
    with pytest.raises(KeyboardInterrupt):
        save_log(make_log(ROWS[:1]), path)
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["log.json"]


def test_failed_replace_keeps_old_file_and_removes_temp(tmp_path, monkeypatch):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    before = path.read_bytes()

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(storage.os, "replace", failing_replace)
    with pytest.raises(OSError):
        save_log(make_log(ROWS[:1]), path)
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["log.json"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_saved_file_is_private(tmp_path):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_save_tightens_permissions_of_existing_file(tmp_path):
    path = tmp_path / "log.json"
    path.write_text("[]")
    os.chmod(path, 0o644)
    save_log(make_log(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_new_data_directory_is_private(tmp_path):
    path = tmp_path / "data" / "log.json"
    save_log(make_log(), path)
    # mkdir's mode is reduced by the umask, but never grants group/other access beyond it.
    assert stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0


# --- Missing and corrupt files -----------------------------------------------

def test_missing_file_gives_empty_log(tmp_path):
    path = tmp_path / "nope" / "log.json"
    assert len(load_log(path)) == 0
    assert not path.exists()  # loading never creates the file


@pytest.mark.parametrize("contents", ["", "  \n"])
def test_empty_file_gives_empty_log(tmp_path, contents):
    path = tmp_path / "log.json"
    path.write_text(contents)
    assert len(load_log(path)) == 0
    assert path.read_text() == contents


@pytest.mark.parametrize("contents", [
    "{not json",                                     # invalid JSON
    '{"date": "2025-07-01"}',                        # not an array
    '[{"date": "2025-07-01", "weight": 200}]',       # missing calories
    '[{"date": "07/01/2025", "weight": 200, "calories": 2200}]',  # bad date
])
def test_corrupt_file_raises_and_is_left_untouched(tmp_path, contents):
    path = tmp_path / "log.json"
    path.write_text(contents)
    with pytest.raises(StorageError, match="Could not read saved data"):
        load_log(path)
    assert path.read_text() == contents


def test_invalid_entries_are_refused_not_dropped(tmp_path):
    # A hand-edited file with a duplicate date must not load as a smaller log
    # (the next save would then silently drop the extra entry).
    path = tmp_path / "log.json"
    rows = [{"date": "2025-07-01", "weight": 200, "calories": 2200},
            {"date": "2025-07-01", "weight": 199, "calories": 2100}]
    path.write_text(json.dumps(rows))
    with pytest.raises(StorageError, match="item 1 .*already exists"):
        load_log(path)


def test_non_utf8_file_raises_storage_error(tmp_path):
    path = tmp_path / "log.json"
    path.write_bytes(b"\xff\xfe\x00garbage")
    with pytest.raises(StorageError):
        load_log(path)


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="POSIX permissions only; root can search any directory")
def test_unsearchable_directory_raises_storage_error(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "log.json").write_text("[]")
    locked.chmod(0)
    try:
        with pytest.raises(StorageError, match="Could not read saved data"):
            load_log(locked / "log.json")
    finally:
        locked.chmod(0o700)
    assert (locked / "log.json").read_text() == "[]"


def test_directory_in_place_of_file_raises_storage_error(tmp_path):
    path = tmp_path / "log.json"
    path.mkdir()
    with pytest.raises(StorageError):
        load_log(path)


# --- Data file location -------------------------------------------------------

def test_default_data_file_is_under_home(isolated_home):
    assert default_data_file() == isolated_home / ".calorie_tracker" / "log.json"
    assert resolve_data_file(None, environ={}) == default_data_file()


def test_default_data_file_is_outside_repo():
    repo = Path(__file__).resolve().parent.parent
    assert repo not in default_data_file().resolve().parents


def test_env_var_overrides_default(tmp_path):
    env = {DATA_FILE_ENV_VAR: str(tmp_path / "env.json")}
    assert resolve_data_file(None, environ=env) == tmp_path / "env.json"


def test_cli_value_overrides_env_var(tmp_path):
    env = {DATA_FILE_ENV_VAR: str(tmp_path / "env.json")}
    assert resolve_data_file(str(tmp_path / "cli.json"), environ=env) == tmp_path / "cli.json"


def test_empty_env_var_falls_back_to_default():
    assert resolve_data_file(None, environ={DATA_FILE_ENV_VAR: ""}) == default_data_file()


def test_data_file_expands_user(isolated_home):
    assert resolve_data_file("~/mine.json", environ={}) == isolated_home / "mine.json"


@pytest.mark.parametrize("name", ["log.csv", "log.txt", "log"])
def test_data_file_must_be_json(tmp_path, name):
    with pytest.raises(ValueError, match=r"\.json"):
        resolve_data_file(str(tmp_path / name), environ={})
