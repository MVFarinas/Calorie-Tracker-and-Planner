import csv
import json
from pathlib import Path
from datetime import datetime
from ..entry import DailyEntry

class FileLoader:
    @staticmethod
    def load_file(filepath: str) -> list[DailyEntry]:
        ext = Path(filepath).suffix.lower()
        if ext == '.csv':
            return FileLoader._load_csv(filepath)
        elif ext == '.json':
            return FileLoader._load_json(filepath)
        elif ext == '.txt':
            return FileLoader._load_txt(filepath)
        else:
            raise ValueError(f'Unsupported file format: {ext or "(none)"}')

    @staticmethod
    def _make_entry(date_str, weight_str, calories_str, source: str) -> DailyEntry:
        # Parse one record into a DailyEntry, raising a clear error that names the
        # offending file/row instead of a bare KeyError/ValueError.
        try:
            date = datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
            weight = float(weight_str)
            calories = int(calories_str)
        except (TypeError, ValueError) as e:
            raise ValueError(f'{source}: could not parse entry '
                             f'(date={date_str!r}, weight={weight_str!r}, calories={calories_str!r}): {e}')
        return DailyEntry(date, weight, calories)

    @staticmethod
    def _load_csv(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for line_no, row in enumerate(reader, start=2):  # line 1 is the header
                FileLoader._require_columns(row, filepath, line_no)
                entries.append(FileLoader._make_entry(
                    row['date'], row['weight'], row['calories'], f'{filepath} line {line_no}'))
        return entries

    @staticmethod
    def _load_json(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r', encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f'{filepath}: expected a JSON array of entries')
        for index, row in enumerate(data):
            FileLoader._require_columns(row, filepath, index)
            entries.append(FileLoader._make_entry(
                row['date'], row['weight'], row['calories'], f'{filepath} item {index}'))
        return entries

    @staticmethod
    def _load_txt(filepath: str) -> list[DailyEntry]:
        # One entry per line as "date, weight, calories" (comma or whitespace
        # separated). Blank lines and lines starting with '#' are ignored, and an
        # optional "date weight calories" header row is skipped.
        entries = []
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_no, raw in enumerate(file, start=1):
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in (line.split(',') if ',' in line else line.split())]
                if parts[:3] == ['date', 'weight', 'calories']:
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
