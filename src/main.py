# main program logic

from util.file_loader import FileLoader
from entry import CaloriesLog, DailyEntry, MaintenanceCalculator

if __name__ == "__main__":
    log = CaloriesLog()

    # Swap between different file formats for testing
    entries = FileLoader.load_file("src/data/sample_data.csv")
    #entries = FileLoader.load_file("src/data/sample_data.json")
    #entries = FileLoader.load_file("src/data/sample_data.txt")

    print("\n--- Loading entries ---")
    for entry in entries:
        log.add_entry(entry)

    maintenance = MaintenanceCalculator(log)
    print(f"\nAverage Daily Calories: {maintenance.maintenance_calculator():.0f}\n")