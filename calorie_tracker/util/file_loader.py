import csv
import json
import math
from datetime import datetime
from pathlib import Path

from ..entry import DailyEntry
from ..units import KG, LBS, kg_to_lbs, normalize_unit

# Largest input file accepted. Years of daily entries fit in well under 1 MB,
# so anything bigger is almost certainly the wrong file.
MAX_FILE_BYTES = 10 * 1024 * 1024

# 'utf-8-sig' also strips the byte-order mark Excel writes at the start of
# CSV files, which would otherwise end up in the first column name.
ENCODING = "utf-8-sig"


class FileLoader:
    @staticmethod
    def load_file(filepath: str, default_unit: str = LBS) -> list[DailyEntry]:
        """Entries from a .csv, .json or .txt file. Weights that don't say their
        unit (no unit/weight_unit field or weight_kg column, and every .txt
        weight) are read in default_unit."""
        return FileLoader.load_file_with_unit_info(filepath, default_unit)[0]

    @staticmethod
    def load_file_with_unit_info(filepath: str, default_unit: str = LBS) -> tuple[list[DailyEntry], int]:
        """Like load_file, but also return how many weights were read in
        default_unit because the file didn't give their unit."""
        default_unit = normalize_unit(default_unit)
        ext = Path(filepath).suffix.lower()
        if ext not in (".csv", ".json", ".txt"):
            raise ValueError(f"Unsupported file format: {ext or '(none)'}")
        size = Path(filepath).stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(
                f"{filepath}: file is too large ({size / 1024 / 1024:.1f} MB); "
                f"the limit is {MAX_FILE_BYTES / 1024 / 1024:.0f} MB"
            )
        if ext == ".csv":
            return FileLoader._load_csv(filepath, default_unit)
        elif ext == ".json":
            return FileLoader._load_json(filepath, default_unit)
        else:
            return FileLoader._load_txt(filepath, default_unit)

    @staticmethod
    def _make_entry(date_str, weight_str, calories_str, source: str, unit=LBS) -> DailyEntry:
        # Parse one record into a DailyEntry, raising a clear error that names the
        # offending file/row instead of a bare KeyError/ValueError. Weights given
        # in kg are converted, since entries always hold lbs.
        try:
            date = datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
            weight = FileLoader._parse_weight(weight_str)
            if normalize_unit(unit) == KG:
                weight = kg_to_lbs(weight)
            calories = FileLoader._parse_calories(calories_str)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"{source}: could not parse entry "
                f"(date={date_str!r}, weight={weight_str!r}, calories={calories_str!r}): {e}"
            ) from e
        return DailyEntry(date, weight, calories)

    @staticmethod
    def _is_blank(value) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _weight_and_unit(row, source: str):
        # A record gives its weight as "weight" (in the unit a "unit" or
        # "weight_unit" field names, or None when neither is given) or as
        # "weight_kg". Returns (weight, unit).
        units = set()
        for key in ("weight_unit", "unit"):
            if key in row and not FileLoader._is_blank(row[key]):
                try:
                    units.add(normalize_unit(row[key]))
                except ValueError as e:
                    raise ValueError(f"{source}: {e}") from e
        if len(units) > 1:
            raise ValueError(f"{source}: weight_unit {row['weight_unit']!r} conflicts with unit {row['unit']!r}")
        unit = units.pop() if units else None
        has_weight = not FileLoader._is_blank(row.get("weight"))
        has_kg = not FileLoader._is_blank(row.get("weight_kg"))
        if has_weight and has_kg:
            raise ValueError(f"{source}: give either weight or weight_kg, not both")
        if has_kg:
            if unit not in (None, KG):
                raise ValueError(f"{source}: weight_kg conflicts with unit {unit!r}")
            return row["weight_kg"], KG
        return row.get("weight"), unit

    @staticmethod
    def _reject_underscores(value, field: str) -> None:
        # int()/float() accept Python digit grouping such as "2_200", which no
        # spreadsheet writes; it is far more likely to be a typo.
        if isinstance(value, str) and "_" in value:
            raise ValueError(f"{field} must be a plain number, got {value!r}")

    @staticmethod
    def _parse_weight(value) -> float:
        # float(True) would silently become 1.0
        if isinstance(value, bool):
            raise ValueError("weight must be a number, not true/false")
        FileLoader._reject_underscores(value, "weight")
        weight = float(value)
        if not math.isfinite(weight):
            raise ValueError(f"weight must be a finite number, got {value!r}")
        return weight

    @staticmethod
    def _parse_calories(value) -> int:
        # Accept whole numbers written as 2200, 2200.0 or "2200", but refuse to
        # truncate a fractional value such as 2200.9.
        if isinstance(value, bool):
            raise ValueError("calories must be a number, not true/false")
        if isinstance(value, int):
            return value
        FileLoader._reject_underscores(value, "calories")
        if isinstance(value, str):
            value = value.strip()
            try:
                return int(value)
            except ValueError:
                pass  # may still be a whole number written as "2200.0"
        number = float(value)
        if not number.is_integer():
            raise ValueError(f"calories must be a whole number, got {value!r}")
        return int(number)

    @staticmethod
    def _load_csv(filepath: str, default_unit: str) -> tuple[list[DailyEntry], int]:
        entries = []
        assumed = 0
        with open(filepath, encoding=ENCODING, newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames:
                # Header names are matched case-insensitively ("Date" or "date").
                reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
            for line_no, row in enumerate(reader, start=2):  # line 1 is the header
                FileLoader._require_columns(row, filepath, line_no)
                source = f"{filepath} line {line_no}"
                weight, unit = FileLoader._weight_and_unit(row, source)
                if unit is None:
                    unit = default_unit
                    assumed += 1
                entries.append(FileLoader._make_entry(row["date"], weight, row["calories"], source, unit))
        return entries, assumed

    @staticmethod
    def _load_json(filepath: str, default_unit: str) -> tuple[list[DailyEntry], int]:
        entries = []
        assumed = 0
        with open(filepath, encoding=ENCODING) as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f"{filepath}: expected a JSON array of entries")
        for index, row in enumerate(data):
            if not isinstance(row, dict):
                raise ValueError(
                    f"{filepath} (item {index}): expected an object with "
                    f"date, weight and calories, got {type(row).__name__}"
                )
            FileLoader._require_columns(row, filepath, index)
            source = f"{filepath} item {index}"
            weight, unit = FileLoader._weight_and_unit(row, source)
            if unit is None:
                unit = default_unit
                assumed += 1
            entries.append(FileLoader._make_entry(row["date"], weight, row["calories"], source, unit))
        return entries, assumed

    @staticmethod
    def _load_txt(filepath: str, default_unit: str) -> tuple[list[DailyEntry], int]:
        # One entry per line as "date, weight, calories" (comma or whitespace
        # separated). Blank lines and lines starting with '#' are ignored, and an
        # optional "date weight calories" header row (any case) is skipped.
        entries = []
        with open(filepath, encoding=ENCODING) as file:
            for line_no, raw in enumerate(file, start=1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in (line.split(",") if "," in line else line.split())]
                if [p.lower() for p in parts[:3]] == ["date", "weight", "calories"]:
                    continue  # header row
                if len(parts) < 3:
                    raise ValueError(
                        f"{filepath} line {line_no}: expected 3 values (date, weight, calories), got {len(parts)}"
                    )
                entries.append(
                    FileLoader._make_entry(parts[0], parts[1], parts[2], f"{filepath} line {line_no}", default_unit)
                )
        # .txt files have no unit column, so every weight is in default_unit.
        return entries, len(entries)

    @staticmethod
    def _require_columns(row, filepath: str, location) -> None:
        required = ("date", "weight", "calories")
        missing = [col for col in required if col not in row or row[col] is None]
        # A weight_kg field stands in for weight.
        if "weight" in missing and row.get("weight_kg") is not None:
            missing.remove("weight")
        if missing:
            raise ValueError(f"{filepath} ({location}): missing required field(s): {', '.join(missing)}")
