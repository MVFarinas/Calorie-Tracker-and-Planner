# main program logic

from util.file_loader import load_file
from entry import CaloriesLog, DailyEntry, MaintenanceCalculator

if __name__ == "__main__":
    log = CaloriesLog()
    entries = load_file()

    for entry in entries:
        log.add_entry(entry)

    maintenance = MaintenanceCalculator(log)
    print(f"Average Daily Calories: {maintenance.maintenance_calculator():.0f}")