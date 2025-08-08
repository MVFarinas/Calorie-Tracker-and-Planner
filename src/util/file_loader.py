'''
Sources: 
1) https://docs.python.org/3/library/csv.html
'''

import csv
import json
from pathlib import Path
from datetime import datetime
from main import DailyEntry

def load_file(filepath):
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
            date_str, weight_str, calories_str = line.strip().split(',')
            date = datetime.strptime(date_str, '%Y-%m-%d')
            weight = float(weight_str)
            calories = int(calories_str)
            entries.append(DailyEntry(date, weight, calories))
    return entries