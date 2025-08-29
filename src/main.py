# main program logic with CLI

from util.file_loader import FileLoader
from entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, EntryValidator, TrendAnalyzer
import logging 
from datetime import datetime

def main():
    log = CaloriesLog()

    while True:
        print("\n=== Maintenance Calorie Finder ===")
        print("1. Add manual entry")
        print("2. Load from file")
        print("3. View summary")
        print("4. Calculate maintenance calories")
        print("5. Plan goal")
        print("6. Analyze trends")
        print("7. Run tests (demo data)")
        print("8. Exit")

        choice = input("Choose an option (1 - 8): ").strip()

        if choice == "1":
            # Manual entry
            date_str = input("Enter date (YYYY-MM-DD): ").strip()
            weight = float(input("Enter weight (lbs): ").strip())
            calories = int(input("Enter calories: ").strip())
            date = datetime.strptime(date_str, "%Y-%m-%d")
            entry = DailyEntry(date, weight, calories)
            log.add_entry(entry)
            print("\nEntry added.")

        elif choice == "2":
            # Load from file
            filepath = input("Enter file path: ").strip()
            try:
                entries = FileLoader.load_file(filepath)
                for e in entries:
                    log.add_entry(e)
                print(f"\nLoaded {len(entries)} entries from {filepath}")
            except Exception as e:
                print(f"\nError loading file: {e}")

        elif choice == "3":
            # Summary
            print("\n--- Summary ---")
            print(f"Days tracked: {log.days_tracked()}")
            print(f"Weight change: {log.weight_difference():.2f} lbs")
            print(f"Average calories: {log.average_calories():.0f}")

        elif choice == "4":
            # Maintenance calories
            calculator = MaintenanceCalculator(log)
            maintenance = calculator.maintenance_calculator()
            print(f"\nEstimated Maintenance Calories: {maintenance:.0f} per day")

        elif choice == "5":
            # Goal planner
            current_weight = float(input("Enter current weight (lbs): ").strip())
            target_weight = float(input("Enter target weight (lbs): ").strip())
            time_frame = int(input("Enter time frame (days): ").strip())
            calculator = MaintenanceCalculator(log)
            maintenance = calculator.maintenance_calculator()
            planner = GoalPlanner(current_weight, target_weight, time_frame, maintenance)
            print(f"\nRecommended Intake (Algebraic): {planner.recommend_calories():.0f}")
            print(f"Recommended Intake (Optimized): {planner.recommend_calories_optimized():.0f}")

        elif choice == "6":
            # Trend analysis
            analyzer = TrendAnalyzer(log)
            window = int(input("Enter moving average window size: ").strip())
            field = input("Analyze 'calories' or 'weight': ").strip().lower()
            averages = analyzer.moving_average(window, field)
            if averages:
                print(f"\nMoving averages for {field} (window={window}):")
                print([round(val, 2) for val in averages])
            else:
                print("\nNot enough data for moving average.")

        elif choice == "7":
            # Demo test mode
            print("\nRunning demo with sample entries...")
            demo_entries = [
                DailyEntry(datetime(2025, 7, 1), 200, 2200),
                DailyEntry(datetime(2025, 7, 2), 198.8, 2200),
                DailyEntry(datetime(2025, 7, 3), 198.2, 2150),
                DailyEntry(datetime(2025, 7, 4), 197.9, 2100),
            ]
            for e in demo_entries:
                log.add_entry(e)
            print("Demo entries added. Try viewing summary or calculating maintenance.")

        elif choice == "8":
            print("\nGoodbye!")
            break

        else:
            print("\nInvalid choice. Please select a number 1 - 8.")

if __name__ == "__main__":
    main()