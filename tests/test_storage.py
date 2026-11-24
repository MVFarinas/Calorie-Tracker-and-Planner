import json
import os
import stat
import sys
from datetime import datetime
from pathlib import Path

import pytest

from calorie_tracker.entry import CaloriesLog, DailyEntry
from calorie_tracker.util import storage
from calorie_tracker.util.file_loader import FileLoader
from calorie_tracker.util.storage import (
    DATA_FILE_ENV_VAR,
    DEFAULT_SETTINGS,
    StorageError,
    default_data_file,
    export_log,
    format_date,
    load_log,
    load_settings,
    resolve_data_file,
    save_log,
    save_settings,
    settings_file_for,
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


# --- Export ---------------------------------------------------------------

def rows_of(entries):
    return [(format_date(e.date), e.weight, e.calories) for e in entries]


@pytest.mark.parametrize("name", ["out.csv", "out.json", "OUT.CSV"])
def test_export_in_lbs_round_trips_exactly(tmp_path, name):
    log = make_log([(1, 200.0, 2200), (2, 199.4, 2100), (5, 1 / 3 + 198, 2000)])
    path = tmp_path / name
    export_log(log, path)
    assert rows_of(FileLoader.load_file(str(path))) == rows_of(log)


@pytest.mark.parametrize("name", ["out.csv", "out.json"])
def test_export_in_kg_round_trips(tmp_path, name):
    log = make_log()
    path = tmp_path / name
    export_log(log, path, unit="kg")
    loaded = FileLoader.load_file(str(path))
    assert [r[0] for r in rows_of(loaded)] == [r[0] for r in rows_of(log)]
    assert [e.weight for e in loaded] == pytest.approx([e.weight for e in log], abs=1e-5)
    assert [e.calories for e in loaded] == [e.calories for e in log]
    # The reloaded entries pass validation again.
    reloaded = CaloriesLog()
    assert all(reloaded.add_entry(e) for e in loaded)


@pytest.mark.parametrize("name", ["out.csv", "out.json"])
def test_export_in_kg_keeps_entries_on_validation_limits(tmp_path, name):
    # Exact 5 lbs/day steps and the 50/600 lb range limits must survive the
    # rounding of kg values and still be accepted when imported again.
    low = [50.0, 55.0, 60.0, 55.0, 50.0]
    high = [575.0, 580.0, 585.0, 590.0, 595.0, 600.0, 595.0]
    climbing = [150.0 + 5 * i for i in range(20)]
    for weights in (low, high, climbing):
        source = [(day, weight, 2200) for day, weight in enumerate(weights, start=1)]
        log = make_log(source)
        path = tmp_path / name
        export_log(log, path, unit="kg")
        reloaded = CaloriesLog()
        loaded = FileLoader.load_file(str(path))
        rejected = [(format_date(e.date), reloaded.rejection_reason(e))
                    for e in loaded if not reloaded.add_entry(e)]
        assert rejected == []
        assert len(reloaded) == len(source)


def test_export_csv_layout_names_the_unit(tmp_path):
    path = tmp_path / "out.csv"
    export_log(make_log([(1, 200.0, 2200)]), path, unit="kg")
    assert path.read_text() == "date,weight,calories,unit\n2025-07-01,90.718474,2200,kg\n"


def test_export_json_layout(tmp_path):
    path = tmp_path / "out.json"
    export_log(make_log([(1, 200.0, 2200)]), path)
    assert json.loads(path.read_text()) == [
        {"date": "2025-07-01", "weight": 200.0, "calories": 2200, "unit": "lbs"}]


def test_export_of_saved_log_reloads_into_same_log(tmp_path):
    # Exported JSON is also a valid data file.
    path = tmp_path / "out.json"
    export_log(make_log(), path, unit="kg")
    assert len(load_log(path)) == len(ROWS)


def test_export_rejects_other_extensions(tmp_path):
    with pytest.raises(ValueError, match=r"\.csv or \.json"):
        export_log(make_log(), tmp_path / "out.txt")
    assert list(tmp_path.iterdir()) == []


def test_export_does_not_create_folders(tmp_path):
    with pytest.raises(OSError):
        export_log(make_log(), tmp_path / "missing" / "out.csv")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions only")
def test_export_is_private(tmp_path):
    path = tmp_path / "out.csv"
    export_log(make_log(), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


# --- Settings -------------------------------------------------------------

def test_settings_file_sits_next_to_data_file(tmp_path):
    assert settings_file_for(tmp_path / "log.json") == tmp_path / "log.settings.json"
    assert settings_file_for(tmp_path / "My.Log.JSON") == tmp_path / "My.Log.settings.json"


def test_missing_settings_give_defaults(tmp_path):
    assert load_settings(tmp_path / "none.json") == DEFAULT_SETTINGS == {"unit": "lbs"}


def test_settings_round_trip(tmp_path):
    path = tmp_path / "sub" / "log.settings.json"
    save_settings({"unit": "kg"}, path)
    assert load_settings(path) == {"unit": "kg"}


@pytest.mark.parametrize("text", ["{oops", "[]", '{"unit": "stone"}', '{"unit": 3}', "\xff"])
def test_bad_settings_fall_back_to_defaults(tmp_path, caplog, text):
    path = tmp_path / "log.settings.json"
    path.write_text(text, encoding="latin-1")
    assert load_settings(path) == DEFAULT_SETTINGS
    assert "settings file" in caplog.text


def test_settings_do_not_change_the_log_schema(tmp_path):
    path = tmp_path / "log.json"
    save_log(make_log(), path)
    save_settings({"unit": "kg"}, settings_file_for(path))
    assert isinstance(json.loads(path.read_text()), list)
    assert len(load_log(path)) == len(ROWS)
