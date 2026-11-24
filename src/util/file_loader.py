import csv
import json
import math
from pathlib import Path
from datetime import datetime
from ..entry import DailyEntry

# Largest input file accepted. Years of daily entries fit in well under 1 MB,
# so anything bigger is almost certainly the wrong file.
MAX_FILE_BYTES = 10 * 1024 * 1024

# 'utf-8-sig' also strips the byte-order mark Excel writes at the start of
# CSV files, which would otherwise end up in the first column name.
ENCODING = 'utf-8-sig'

class FileLoader:
    @staticmethod
    def load_file(filepath: str) -> list[DailyEntry]:
        ext = Path(filepath).suffix.lower()
        if ext not in ('.csv', '.json', '.txt'):
            raise ValueError(f'Unsupported file format: {ext or "(none)"}')
        size = Path(filepath).stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f'{filepath}: file is too large ({size / 1024 / 1024:.1f} MB); '
                             f'the limit is {MAX_FILE_BYTES / 1024 / 1024:.0f} MB')
        if ext == '.csv':
            return FileLoader._load_csv(filepath)
        elif ext == '.json':
            return FileLoader._load_json(filepath)
        else:
            return FileLoader._load_txt(filepath)

    @staticmethod
    def _make_entry(date_str, weight_str, calories_str, source: str) -> DailyEntry:
        # Parse one record into a DailyEntry, raising a clear error that names the
        # offending file/row instead of a bare KeyError/ValueError.
        try:
            date = datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
            weight = FileLoader._parse_weight(weight_str)
            calories = FileLoader._parse_calories(calories_str)
        except (TypeError, ValueError) as e:
            raise ValueError(f'{source}: could not parse entry '
                             f'(date={date_str!r}, weight={weight_str!r}, calories={calories_str!r}): {e}')
        return DailyEntry(date, weight, calories)

    @staticmethod
    def _reject_underscores(value, field: str) -> None:
        # int()/float() accept Python digit grouping such as "2_200", which no
        # spreadsheet writes; it is far more likely to be a typo.
        if isinstance(value, str) and '_' in value:
            raise ValueError(f'{field} must be a plain number, got {value!r}')

    @staticmethod
    def _parse_weight(value) -> float:
        # float(True) would silently become 1.0
        if isinstance(value, bool):
            raise ValueError('weight must be a number, not true/false')
        FileLoader._reject_underscores(value, 'weight')
        weight = float(value)
        if not math.isfinite(weight):
            raise ValueError(f'weight must be a finite number, got {value!r}')
        return weight

    @staticmethod
    def _parse_calories(value) -> int:
        # Accept whole numbers written as 2200, 2200.0 or "2200", but refuse to
        # truncate a fractional value such as 2200.9.
        if isinstance(value, bool):
            raise ValueError('calories must be a number, not true/false')
        if isinstance(value, int):
            return value
        FileLoader._reject_underscores(value, 'calories')
        if isinstance(value, str):
            value = value.strip()
            try:
                return int(value)
            except ValueError:
                pass  # may still be a whole number written as "2200.0"
        number = float(value)
        if not number.is_integer():
            raise ValueError(f'calories must be a whole number, got {value!r}')
        return int(number)

    @staticmethod
    def _load_csv(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r', encoding=ENCODING, newline='') as file:
            reader = csv.DictReader(file)
            if reader.fieldnames:
                # Header names are matched case-insensitively ("Date" or "date").
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
            for line_no, row in enumerate(reader, start=2):  # line 1 is the header
                FileLoader._require_columns(row, filepath, line_no)
                entries.append(FileLoader._make_entry(
                    row['date'], row['weight'], row['calories'], f'{filepath} line {line_no}'))
        return entries

    @staticmethod
    def _load_json(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r', encoding=ENCODING) as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f'{filepath}: expected a JSON array of entries')
        for index, row in enumerate(data):
            if not isinstance(row, dict):
                raise ValueError(f'{filepath} (item {index}): expected an object with '
                                 f'date, weight and calories, got {type(row).__name__}')
            FileLoader._require_columns(row, filepath, index)
            entries.append(FileLoader._make_entry(
                row['date'], row['weight'], row['calories'], f'{filepath} item {index}'))
        return entries

    @staticmethod
    def _load_txt(filepath: str) -> list[DailyEntry]:
        # One entry per line as "date, weight, calories" (comma or whitespace
        # separated). Blank lines and lines starting with '#' are ignored, and an
        # optional "date weight calories" header row (any case) is skipped.
        entries = []
        with open(filepath, 'r', encoding=ENCODING) as file:
            for line_no, raw in enumerate(file, start=1):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in (line.split(',') if ',' in line else line.split())]
                if [p.lower() for p in parts[:3]] == ['date', 'weight', 'calories']:
                    continue  # header row
                if len(parts) < 3:
                    raise ValueError(f'{filepath} line {line_no}: expected 3 values '
                                     f'(date, weight, calories), got {len(parts)}')
                entries.append(FileLoader._make_entry(
                    parts[0], parts[1], parts[2], f'{filepath} line {line_no}'))
        return entries

    @staticmethod
    def _require_columns(row, filepath: str, location) -> None:
        required = ('date', 'weight', 'calories')
        missing = [col for col in required if col not in row or row[col] is None]
        if missing:
            raise ValueError(f'{filepath} ({location}): missing required field(s): {", ".join(missing)}')
