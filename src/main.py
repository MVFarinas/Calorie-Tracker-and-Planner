# main program logic with CLI

from .util.file_loader import FileLoader
from .util.storage import DATA_FILE_ENV_VAR, StorageError, load_log, resolve_data_file, save_log
from .entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, TrendAnalyzer
from collections import Counter
from datetime import datetime
from pathlib import Path
import argparse
import logging
import math
import sys

DEMO_DATA = Path(__file__).parent / "data" / "sample_data.csv"

MENU_OPTIONS = (
    "Add manual entry",
    "Load from file",
    "View summary",
    "Calculate maintenance calories",
    "Plan goal",
    "Analyze trends",
    "Load demo data",
    "List entries",
    "Edit entry",
    "Delete entry",
    "Exit",
)
EXIT_CHOICE = str(len(MENU_OPTIONS))

GOAL_DISCLAIMER = ("Note: these are estimates only, not medical advice. Check with a doctor "
                   "or registered dietitian before making big changes to your diet.")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m src.main",
                                     description="Estimate maintenance calories and plan weight goals.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show debug logging, including details of every entry added or rejected")
    parser.add_argument("--data-file", metavar="PATH",
                        help=f"JSON file the log is saved to and loaded from (default: ${DATA_FILE_ENV_VAR} "
                             "if set, otherwise ~/.calorie_tracker/log.json)")
    return parser.parse_args(argv)


def configure_logging(verbose: bool = False) -> None:
    # Warnings only by default: debug messages include personal weight and calorie data.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")


def prompt_float(prompt: str) -> float:
    while True:
        try:
            value = float(input(prompt).strip())
        except ValueError:
            print("Please enter a valid number.")
            continue
        if not math.isfinite(value):  # float() accepts "nan" and "inf"
            print("Please enter a valid number.")
            continue
        return value


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


def add_entries(log: CaloriesLog, entries) -> tuple[int, Counter]:
    """Add each entry to the log; return how many were added and a count of rejection reasons."""
    added = 0
    skipped = Counter()
    for entry in entries:
        if log.add_entry(entry):
            added += 1
        else:
            skipped[log.rejection_reason(entry)] += 1
    return added, skipped


def print_skipped(skipped: Counter) -> None:
    for reason, count in skipped.most_common():
        print(f"  Skipped {count}: {reason}")


def format_entry(entry: DailyEntry) -> str:
    return f"{entry.date:%Y-%m-%d}  {entry.weight:g} lbs  {entry.calories} cals"


def list_entries(log: CaloriesLog) -> None:
    if len(log) == 0:
        print("\nNo entries yet.")
        return
    print(f"\n--- Entries ({len(log)}) ---")
    for entry in log:
        print(f"  {format_entry(entry)}")


def edit_entry(log: CaloriesLog) -> bool:
    """Ask for a date and new values; return True when the log was changed."""
    if len(log) == 0:
        print("\nNo entries to edit.")
        return False
    date = prompt_date("Enter date of the entry to edit (YYYY-MM-DD): ")
    entry = log.get_entry(date)
    if entry is None:
        print(f"\nNo entry for {date:%Y-%m-%d}.")
        return False
    print(f"Current: {format_entry(entry)}")
    weight = prompt_float("Enter new weight (lbs): ")
    calories = prompt_int("Enter new calories: ")
    if log.update_entry(date, weight, calories):
        print("\nEntry updated.")
        return True
    print(f"\nEntry not updated: {log.update_rejection_reason(date, weight, calories)}.")
    return False


def delete_entry(log: CaloriesLog) -> bool:
    """Ask for a date and confirmation; return True when the log was changed."""
    if len(log) == 0:
        print("\nNo entries to delete.")
        return False
    date = prompt_date("Enter date of the entry to delete (YYYY-MM-DD): ")
    entry = log.get_entry(date)
    if entry is None:
        print(f"\nNo entry for {date:%Y-%m-%d}.")
        return False
    answer = input(f"Delete {format_entry(entry)}? (y/N): ").strip().lower()
    if answer not in ("y", "yes"):
        print("\nNot deleted.")
        return False
    log.remove_entry(date)
    print("\nEntry deleted.")
    return True


def main(data_file=None) -> int:
    """Run the interactive menu. With data_file, the log is loaded from it at
    startup and saved back after every change; without it nothing is persisted.
    Returns the process exit status."""
    if data_file is None:
        log = CaloriesLog()
    else:
        is_new = not Path(data_file).exists()
        try:
            log = load_log(data_file)
        except StorageError as e:
            # Refuse to start rather than risk overwriting the file with an empty log.
            print(f"Error: {e}", file=sys.stderr)
            print("Fix or move that file, or use --data-file to choose another one.", file=sys.stderr)
            return 1
        if is_new:
            print(f"No saved entries yet. Changes will be saved to {data_file}")
        else:
            print(f"Loaded {len(log)} saved entries from {data_file}")

    def save():
        if data_file is None:
            return
        try:
            save_log(log, data_file)
        except OSError as e:
            print(f"Warning: could not save to {data_file}: {e}. "
                  f"Changes since the last successful save are not saved yet.")

    while True:
        print("\n=== Maintenance Calorie Finder ===")
        for number, label in enumerate(MENU_OPTIONS, start=1):
            print(f"{number}. {label}")

        try:
            choice = input(f"Choose an option (1 - {EXIT_CHOICE}): ").strip()

            if choice == "1":
                # Manual entry
                date = prompt_date("Enter date (YYYY-MM-DD): ")
                weight = prompt_float("Enter weight (lbs): ")
                calories = prompt_int("Enter calories: ")
                entry = DailyEntry(date, weight, calories)
                if log.add_entry(entry):
                    print("\nEntry added.")
                    save()
                else:
                    print(f"\nEntry rejected: {log.rejection_reason(entry)}.")

            elif choice == "2":
                # Load from file
                filepath = input("Enter file path: ").strip()
                try:
                    entries = FileLoader.load_file(filepath)
                    added, skipped = add_entries(log, entries)
                    print(f"\nLoaded {added} of {len(entries)} entries from {filepath}")
                    print_skipped(skipped)
                except Exception as e:
                    print(f"\nError loading file: {e}")
                else:
                    if added:
                        save()

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
                added, skipped = add_entries(log, demo_entries)
                print(f"Added {added} of {len(demo_entries)} demo entries. Try viewing summary or calculating maintenance.")
                print_skipped(skipped)
                if added:
                    save()

            elif choice == "8":
                list_entries(log)

            elif choice == "9":
                if edit_entry(log):
                    save()

            elif choice == "10":
                if delete_entry(log):
                    save()

            elif choice == EXIT_CHOICE:
                print("\nGoodbye!")
                break

            else:
                print(f"\nInvalid choice. Please select a number 1 - {EXIT_CHOICE}.")

        except (EOFError, KeyboardInterrupt):
            # Every change is saved as it is made, so there is nothing to flush here.
            print("\nGoodbye!")
            break

    return 0


def run(argv=None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    try:
        data_file = resolve_data_file(args.data_file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return main(data_file)


if __name__ == "__main__":
    sys.exit(run())
