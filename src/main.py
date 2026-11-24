# main program logic with CLI

from .util.file_loader import FileLoader
from .entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, TrendAnalyzer
from datetime import datetime
from pathlib import Path
import argparse
import logging

DEMO_DATA = Path(__file__).parent / "data" / "sample_data.csv"

GOAL_DISCLAIMER = ("Note: these are estimates only, not medical advice. Check with a doctor "
                   "or registered dietitian before making big changes to your diet.")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m src.main",
                                     description="Estimate maintenance calories and plan weight goals.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show debug logging, including details of every entry added or rejected")
    return parser.parse_args(argv)


def configure_logging(verbose: bool = False) -> None:
    # Warnings only by default: debug messages include personal weight and calorie data.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")


def prompt_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt).strip())
        except ValueError:
            print("Please enter a valid number.")


def prompt_int(prompt: str, minimum: int = None) -> int:
    while True:
        try:
            value = int(input(prompt).strip())
        except ValueError:
            print("Please enter a valid whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Please enter a whole number of at least {minimum}.")
            continue
        return value


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
                    time_frame = prompt_int("Enter time frame (days): ", minimum=1)
                    planner = GoalPlanner(current_weight, target_weight, time_frame, maintenance)
                    print(f"\nRecommended Intake (Algebraic): {planner.recommend_calories():.0f}")
                    print(f"Recommended Intake (Optimized): {planner.recommend_calories_optimized():.0f}")
                    for warning in planner.safety_warnings():
                        print(f"Warning: {warning}")
                    print(f"\n{GOAL_DISCLAIMER}")

            elif choice == "6":
                # Trend analysis
                analyzer = TrendAnalyzer(log)
                window = prompt_int("Enter moving average window size: ", minimum=1)
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
                # Demo data: the bundled 20-day sample, enough for a stable estimate
                print("\nLoading demo entries...")
                demo_entries = FileLoader.load_file(str(DEMO_DATA))
                added = sum(1 for e in demo_entries if log.add_entry(e))
                print(f"Added {added} of {len(demo_entries)} demo entries. Try viewing summary or calculating maintenance.")

            elif choice == "8":
                print("\nGoodbye!")
                break

            else:
                print("\nInvalid choice. Please select a number 1 - 8.")

        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    configure_logging(parse_args().verbose)
    main()
