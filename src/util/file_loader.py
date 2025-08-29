import csv
import json
from pathlib import Path
from datetime import datetime
from entry import DailyEntry

class FileLoader:
    def load_file(filepath: str):
        ext = Path(filepath).suffix.lower()
        if ext == '.csv':
            return load_csv(filepath)
        elif ext == '.json':
            return load_json(filepath)
        elif ext == '.txt':
            return load_txt(filepath)
        else:
            raise ValueError(f'Unsupported file format')
    
    def load_csv(filepath):
        entries = []
        with open(filepath, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                weight = float(row['weight'])
                calories = int(row['calories'])
                entries.append(DailyEntry(date, weight, calories))
        return entries
    
    def load_json(filepath):
        entries = []
        with open(filepath, 'r') as file:
            data = json.load(file)
            for row in data:
                date = datetime.strptime(row['date'], '%Y-%m-%d')
                weight = float(row['weight'])
                calories = int(row['calories'])
                entries.append(DailyEntry(date, weight, calories))
        return entries

    def load_txt(filepath):
        entries = []
        with open(filepath, 'r') as file:
            for line in file:

                # normalize delimiters and split
                parts = line.replace(',', ' ').split()

                #skip empty lines
                if len(parts) < 3:
                    continue

                # parse date, weight, and calories
                date_str, weight_str, calories_str = parts[0], parts[1], parts[2]

                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d')
                    weight = float(weight_str)
                    calories = int(calories_str)
                    entries.append(DailyEntry(date, weight, calories))
                except (ValueError, TypeError): #skip invalid rows
                    continue # dont crash on invalid data
        return entries