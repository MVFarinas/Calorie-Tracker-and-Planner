"""Save and load the log between CLI sessions.

The data file uses the same schema the JSON importer reads
([{"date": "YYYY-MM-DD", "weight": ..., "calories": ...}, ...]), so a saved
log can also be imported with FileLoader.
"""

import json
import os
import tempfile
from pathlib import Path

from ..entry import CaloriesLog
from .file_loader import FileLoader

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
    # Resolve symlinks first, or os.replace would swap the link for a regular file.
    path = Path(os.path.realpath(path))
    path.parent.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    data = [{"date": format_date(entry.date), "weight": float(entry.weight),
             "calories": int(entry.calories)} for entry in log]

    # mkstemp creates the file with mode 0o600 on POSIX, so it is never readable
    # by others, even briefly; chmod again in case the platform differs.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
            file.write("\n")
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
