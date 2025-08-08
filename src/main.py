# main program logic

from util.file_loader import load_file
from entry import CaloriesLog, DailyEntry, MaintenanceCalculator

if __name__ == "__main__":
    log = CaloriesLog()

    # Swap between different file formats for testing
    entries = load_file("data/sample_data.csv")
    #entries = load_file("data/sample_data.json")
    #entries = load_file("data/sample_data.txt")

    for entry in entries:
        log.add_entry(entry)

    maintenance = MaintenanceCalculator(log)
    print(f"Average Daily Calories: {maintenance.maintenance_calculator():.0f}")