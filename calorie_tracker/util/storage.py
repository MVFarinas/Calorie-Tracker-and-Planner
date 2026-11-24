"""Save and load the log between CLI sessions.

The data file uses the same schema the JSON importer reads
([{"date": "YYYY-MM-DD", "weight": ..., "calories": ...}, ...]), so a saved
log can also be imported with FileLoader. Preferences such as the weight unit
live in a separate settings file next to it (see settings_file_for), so the
log itself stays a plain array of entries.
"""

import csv
import json
import logging
import os
import tempfile
from pathlib import Path

from ..entry import CaloriesLog
from ..units import KG, LBS, from_lbs, normalize_unit
from .file_loader import FileLoader

logger = logging.getLogger(__name__)

DATA_FILE_ENV_VAR = "CALORIE_TRACKER_DATA"

# The file holds personal health data, so only the owner may read or write it.
FILE_MODE = 0o600
DIR_MODE = 0o700


class StorageError(Exception):
    """The data file exists but can't be read or doesn't hold a valid log."""


def default_data_file() -> Path:
    # Evaluated on each call (not at import) so HOME can be changed, e.g. in tests.
    return Path.home() / ".calorie_tracker" / "log.json"


def resolve_data_file(cli_value=None, environ=None) -> Path:
    """Data file location: the --data-file value, else $CALORIE_TRACKER_DATA,
    else default_data_file(). Raises ValueError unless it ends in .json, which
    keeps the saved file importable with FileLoader."""
    environ = os.environ if environ is None else environ
    value = cli_value or environ.get(DATA_FILE_ENV_VAR) or default_data_file()
    path = Path(value).expanduser()
    if path.suffix.lower() != ".json":
        raise ValueError(f"Data file must be a .json file, got {str(path)!r}")
    return path


def format_date(date) -> str:
    # isoformat() always pads the year to four digits; strftime("%Y") doesn't on
    # every platform (glibc writes year 225 as "225"), and the loader needs four.
    return date.date().isoformat()


def load_log(path) -> CaloriesLog:
    """Load a saved log. A missing, empty or whitespace-only file gives an empty
    log; anything else that can't be read back exactly (unreadable file, bad JSON,
    wrong schema, entries that fail validation) raises StorageError, so the caller
    never overwrites it with a partial log."""
    path = Path(path)
    log = CaloriesLog()
    try:
        # Not path.exists(): it raises PermissionError when the directory can't be
        # searched, and only a file that is really absent counts as a new log.
        os.stat(path)
    except FileNotFoundError:
        return log
    except OSError as e:
        raise StorageError(f"Could not read saved data from {path}: {e}") from e
    try:
        if not path.read_bytes().strip():
            return log  # nothing to protect, e.g. created with `touch`
        entries = FileLoader.load_file(str(path))
    except (OSError, ValueError, TypeError) as e:
        # json.JSONDecodeError and UnicodeDecodeError are both ValueErrors.
        raise StorageError(f"Could not read saved data from {path}: {e}") from e
    for index, entry in enumerate(entries):
        if not log.add_entry(entry):
            raise StorageError(f"Saved data in {path} is invalid: item {index} "
                               f"({format_date(entry.date)}) was rejected: {log.rejection_reason(entry)}")
    return log


def save_log(log: CaloriesLog, path) -> None:
    """Write the log to path atomically: the data goes to a temporary file in the
    same directory, which then replaces the old file in one step, so an
    interrupted save leaves the previous file intact. If path is a symlink, the
    file it points to is updated and the link is kept."""
    data = [{"date": format_date(entry.date), "weight": float(entry.weight),
             "calories": int(entry.calories)} for entry in log]
    _write_atomic(path, lambda file: _dump_json(data, file))


def _dump_json(data, file) -> None:
    json.dump(data, file, indent=2)
    file.write("\n")


def _write_atomic(path, write, make_parents: bool = True) -> None:
    # write(file) fills the temporary file, which then replaces path.
    # Resolve symlinks first, or os.replace would swap the link for a regular file.
    path = Path(os.path.realpath(path))
    if make_parents:
        path.parent.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)

    # mkstemp creates the file with mode 0o600 on POSIX, so it is never readable
    # by others, even briefly; chmod again in case the platform differs.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
            write(file)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(tmp_name, FILE_MODE)
        os.replace(tmp_name, path)
    except BaseException:
        # Also on KeyboardInterrupt: don't leave the temporary file behind.
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    _fsync_dir(path.parent)


# --- Export ---------------------------------------------------------------

EXPORT_FORMATS = (".csv", ".json")

# Decimal places kept when exporting in kg: well below a gram, and enough to
# turn 90.49999999999999 back into 90.5. The few millionths of a pound this
# can add on import are within EntryValidator's weight tolerance, so entries on
# a validation limit are still accepted when the export is read back.
KG_EXPORT_DECIMALS = 6


def export_log(log: CaloriesLog, path, unit: str = LBS) -> None:
    """Write every entry to a .csv or .json file that FileLoader can import again.
    Weights are written in `unit`, and each record names its unit, so the file
    reads back the same whichever unit the importer prefers. Raises ValueError
    for any other extension and OSError when the file can't be written (the
    folder must already exist). An existing file is replaced; asking first is
    up to the caller."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in EXPORT_FORMATS:
        raise ValueError(f"Export file must end in .csv or .json, got {str(path)!r}")
    unit = normalize_unit(unit)
    rows = []
    for entry in log:
        weight = from_lbs(float(entry.weight), unit)
        if unit == KG:
            weight = round(weight, KG_EXPORT_DECIMALS)
        rows.append({"date": format_date(entry.date), "weight": weight,
                     "calories": int(entry.calories), "unit": unit})
    if ext == ".json":
        _write_atomic(path, lambda file: _dump_json(rows, file), make_parents=False)
    else:
        _write_atomic(path, lambda file: _write_csv(rows, file), make_parents=False)


def _write_csv(rows, file) -> None:
    writer = csv.DictWriter(file, fieldnames=["date", "weight", "calories", "unit"],
                            lineterminator="\n")
    writer.writeheader()
    # str(float) is the shortest text that reads back as the same float, so
    # lbs values round-trip exactly.
    writer.writerows(rows)


# --- Settings -------------------------------------------------------------

DEFAULT_SETTINGS = {"unit": LBS}


def settings_file_for(data_file) -> Path:
    """Settings file kept next to the data file: log.json -> log.settings.json."""
    data_file = Path(data_file)
    return data_file.with_name(f"{data_file.stem}.settings.json")


def load_settings(path) -> dict:
    """Saved settings merged over DEFAULT_SETTINGS. A missing file gives the
    defaults; an unreadable or invalid one is logged and also gives the defaults,
    since nothing in it is worth refusing to start over."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as e:
        logger.warning("Ignoring settings file %s: %s", path, e)
        return settings
    if not isinstance(data, dict):
        logger.warning("Ignoring settings file %s: expected a JSON object", path)
        return settings
    if "unit" in data:
        try:
            settings["unit"] = normalize_unit(data["unit"])
        except ValueError as e:
            logger.warning("Ignoring unit in settings file %s: %s", path, e)
    return settings


def save_settings(settings: dict, path) -> None:
    """Write settings atomically (same guarantees as save_log)."""
    _write_atomic(path, lambda file: _dump_json(settings, file))


def _fsync_dir(directory: Path) -> None:
    # Make the rename itself durable. Not supported on Windows, where it's skipped.
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
