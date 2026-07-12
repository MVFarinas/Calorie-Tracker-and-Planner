# main program logic with CLI

from .util.file_loader import FileLoader
from .entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, TrendAnalyzer
from datetime import datetime


def prompt_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("Please enter a valid number.")


def prompt_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("Please enter a valid whole number.")


def prompt_date(prompt: str) -> datetime:
    while True:
        try:
            return datetime.strptime(input(prompt).strip(), "%Y-%m-%d")
        except ValueError:
            print("Please enter a date in YYYY-MM-DD format.")


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
        print("7. Load demo data")
        print("8. Exit")

        try:
            choice = input("Choose an option (1 - 8): ").strip()

            if choice == "1":
                # Manual entry
                date = prompt_date("Enter date (YYYY-MM-DD): ")
                weight = prompt_float("Enter weight (lbs): ")
                calories = prompt_int("Enter calories: ")
                entry = DailyEntry(date, weight, calories)
                if log.add_entry(entry):
                    print("\nEntry added.")
                else:
                    print("\nEntry rejected (failed validation).")

            elif choice == "2":
                # Load from file
                filepath = input("Enter file path: ").strip()
                try:
                    entries = FileLoader.load_file(filepath)
                    added = sum(1 for e in entries if log.add_entry(e))
                    print(f"\nLoaded {added} of {len(entries)} entries from {filepath}")
                except Exception as e:
                    print(f"\nError loading file: {e}")

            elif choice == "3":
                # Summary
                weight_change = log.weight_difference()
                avg_calories = log.average_calories()
                print("\n--- Summary ---")
                print(f"Days tracked: {log.days_tracked()}")
                print(f"Weight change: {weight_change:.2f} lbs" if weight_change is not None else "Weight change: N/A (need at least 2 entries)")
                print(f"Average calories: {avg_calories:.0f}" if avg_calories is not None else "Average calories: N/A (no entries)")

            elif choice == "4":
                # Maintenance calories
                calculator = MaintenanceCalculator(log)
                maintenance = calculator.maintenance_calculator()
                if maintenance is None:
                    print("\nNot enough data to estimate maintenance calories (need at least 2 entries).")
                else:
                    print(f"\nEstimated Maintenance Calories: {maintenance:.0f} per day")

            elif choice == "5":
                # Goal planner
                calculator = MaintenanceCalculator(log)
                maintenance = calculator.maintenance_calculator()
                if maintenance is None:
                    print("\nNot enough data to plan a goal yet (need at least 2 entries to estimate maintenance).")
                else:
                    current_weight = prompt_float("Enter current weight (lbs): ")
                    target_weight = prompt_float("Enter target weight (lbs): ")
                    time_frame = prompt_int("Enter time frame (days): ")
                    planner = GoalPlanner(current_weight, target_weight, time_frame, maintenance)
                    print(f"\nRecommended Intake (Algebraic): {planner.recommend_calories():.0f}")
                    print(f"Recommended Intake (Optimized): {planner.recommend_calories_optimized():.0f}")

            elif choice == "6":
                # Trend analysis
                analyzer = TrendAnalyzer(log)
                window = prompt_int("Enter moving average window size: ")
                field = input("Analyze 'calories' or 'weight': ").strip().lower()
                if field not in ("calories", "weight"):
                    print("\nPlease choose 'calories' or 'weight'.")
                    continue
                averages = analyzer.moving_average(window, field)
                if averages:
                    print(f"\nMoving averages for {field} (window={window}):")
                    print([round(val, 2) for val in averages])
                else:
                    print("\nNot enough data for moving average.")

            elif choice == "7":
                # Demo data
                print("\nLoading demo entries...")
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

        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()
