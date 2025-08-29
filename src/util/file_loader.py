import csv
import json
from pathlib import Path
from datetime import datetime
from entry import DailyEntry

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
            raise ValueError(f'Unsupported file format')

    @staticmethod
    def _load_csv(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                weight = float(row['weight'])
                calories = int(row['calories'])
                entries.append(DailyEntry(date, weight, calories))
        return entries

    @staticmethod
    def _load_json(filepath: str) -> list[DailyEntry]:
        entries = []
        with open(filepath, 'r') as file:
            data = json.load(file)
            for row in data:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                weight = float(row['weight'])
                calories = int(row['calories'])
                entries.append(DailyEntry(date, weight, calories))
        return entries