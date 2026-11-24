# main program logic with CLI

import argparse
import logging
import math
import os
import shutil
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from .chart import DEFAULT_WIDTH, render_weight_chart
from .entry import CaloriesLog, DailyEntry, GoalPlanner, MaintenanceCalculator, TrendAnalyzer
from .units import LBS, format_weight, from_lbs, normalize_unit, to_lbs
from .util.file_loader import FileLoader
from .util.storage import (
    DATA_FILE_ENV_VAR,
    DEFAULT_SETTINGS,
    EXPORT_FORMATS,
    StorageError,
    export_log,
    format_date,
    load_log,
    load_settings,
    resolve_data_file,
    save_log,
    save_settings,
    settings_file_for,
)

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
    "Export entries",
    "Change weight unit",
    "Exit",
)
EXIT_CHOICE = str(len(MENU_OPTIONS))

GOAL_DISCLAIMER = (
    "Note: these are estimates only, not medical advice. Check with a doctor "
    "or registered dietitian before making big changes to your diet."
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="calorie-tracker", description="Estimate maintenance calories and plan weight goals."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show debug logging, including details of every entry added or rejected",
    )
    parser.add_argument(
        "--data-file",
        metavar="PATH",
        help=f"JSON file the log is saved to and loaded from (default: ${DATA_FILE_ENV_VAR} "
        "if set, otherwise ~/.calorie_tracker/log.json)",
    )
    parser.add_argument(
        "--units",
        type=_unit_arg,
        metavar="{lbs,kg}",
        help="show and enter weights in this unit for this session "
        "(default: the unit last chosen in the menu, otherwise lbs)",
    )
    return parser.parse_args(argv)


def _unit_arg(value: str) -> str:
    try:
        return normalize_unit(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e


def configure_logging(verbose: bool = False) -> None:
    # Warnings only by default: debug messages include personal weight and calorie data.
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format="%(levelname)s: %(message)s")


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


def prompt_int(prompt: str, minimum: int | None = None) -> int:
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


def add_entries(log: CaloriesLog, entries: Iterable[DailyEntry]) -> tuple[int, Counter[str | None]]:
    """Add each entry to the log; return how many were added and a count of rejection reasons."""
    added = 0
    skipped: Counter[str | None] = Counter()
    for entry in entries:
        if log.add_entry(entry):
            added += 1
        else:
            skipped[log.rejection_reason(entry)] += 1
    return added, skipped


def print_skipped(skipped: Counter[str | None]) -> None:
    for reason, count in skipped.most_common():
        print(f"  Skipped {count}: {reason}")


def ask_file_unit(count: int) -> str:
    """Ask which unit `count` weights that don't name their unit are in; Enter means lbs."""
    noun = "weight doesn't" if count == 1 else "weights don't"
    while True:
        answer = input(f"{count} {noun} say their unit. Are they in lbs or kg? (lbs/kg, Enter for lbs): ").strip()
        if not answer:
            return LBS
        try:
            return normalize_unit(answer)
        except ValueError:
            print("Please enter 'lbs' or 'kg'.")


def prompt_weight(prompt: str, unit: str) -> float:
    """Ask for a weight in `unit` and return it in lbs, the unit entries are stored in."""
    return to_lbs(prompt_float(f"{prompt} ({unit}): "), unit)


def format_entry(entry: DailyEntry, unit: str = LBS) -> str:
    return f"{format_date(entry.date)}  {format_weight(entry.weight, unit)}  {entry.calories} cals"


def list_entries(log: CaloriesLog, unit: str = LBS) -> None:
    if len(log) == 0:
        print("\nNo entries yet.")
        return
    print(f"\n--- Entries ({len(log)}) ---")
    for entry in log:
        print(f"  {format_entry(entry, unit)}")


def edit_entry(log: CaloriesLog, unit: str = LBS) -> bool:
    """Ask for a date and new values; return True when the log was changed."""
    if len(log) == 0:
        print("\nNo entries to edit.")
        return False
    date = prompt_date("Enter date of the entry to edit (YYYY-MM-DD): ")
    entry = log.get_entry(date)
    if entry is None:
        print(f"\nNo entry for {format_date(date)}.")
        return False
    print(f"Current: {format_entry(entry, unit)}")
    weight = prompt_weight("Enter new weight", unit)
    calories = prompt_int("Enter new calories: ")
    if log.update_entry(date, weight, calories):
        print("\nEntry updated.")
        return True
    print(f"\nEntry not updated: {log.update_rejection_reason(date, weight, calories)}.")
    return False


def delete_entry(log: CaloriesLog, unit: str = LBS) -> bool:
    """Ask for a date and confirmation; return True when the log was changed."""
    if len(log) == 0:
        print("\nNo entries to delete.")
        return False
    date = prompt_date("Enter date of the entry to delete (YYYY-MM-DD): ")
    entry = log.get_entry(date)
    if entry is None:
        print(f"\nNo entry for {format_date(date)}.")
        return False
    answer = input(f"Delete {format_entry(entry, unit)}? (y/N): ").strip().lower()
    if answer not in ("y", "yes"):
        print("\nNot deleted.")
        return False
    log.remove_entry(date)
    print("\nEntry deleted.")
    return True


def export_entries(log: CaloriesLog, unit: str = LBS, data_file=None) -> None:
    """Ask for a .csv or .json path and write every entry to it, asking before
    replacing an existing file."""
    if len(log) == 0:
        print("\nNo entries to export.")
        return
    answer = input("Enter export file path (.csv or .json): ").strip()
    if not answer:
        print("\nNothing exported.")
        return
    path = Path(answer).expanduser()
    if path.suffix.lower() not in EXPORT_FORMATS:
        print("\nThe export file must end in .csv or .json.")
        return
    # The path checks raise ValueError too, e.g. for a NUL character in the path.
    try:
        if data_file is not None and os.path.realpath(path) in (
            os.path.realpath(data_file),
            os.path.realpath(settings_file_for(data_file)),
        ):
            print("\nThat file holds your saved log or settings; choose another path.")
            return
        if os.path.isdir(path):
            print(f"\n{path} is a folder; enter a file path.")
            return
        if os.path.lexists(path):
            confirm = input(f"{path} already exists. Overwrite it? (y/N): ").strip().lower()
            if confirm not in ("y", "yes"):
                print("\nNothing exported.")
                return
        export_log(log, path, unit)
    except (OSError, ValueError) as e:
        print(f"\nCould not export to {path}: {e}")
        return
    noun = "entry" if len(log) == 1 else "entries"
    print(f"\nExported {len(log)} {noun} to {path} (weights in {unit}).")


def chart_width() -> int:
    # Fit narrower terminals, but never go past ~80 columns.
    return min(DEFAULT_WIDTH, shutil.get_terminal_size().columns - 1)


def analyze_trends(log: CaloriesLog, unit: str = LBS) -> None:
    analyzer = TrendAnalyzer(log)
    print("\n--- Trend Analysis ---")
    print("1. Moving average")
    print("2. Weight trend chart")
    choice = input("Choose an option (1 - 2): ").strip()

    if choice == "1":
        window = prompt_int("Enter moving average window size: ", minimum=1)
        field = input("Analyze 'calories' or 'weight': ").strip().lower()
        if field not in ("calories", "weight"):
            print("\nPlease choose 'calories' or 'weight'.")
            return
        averages = analyzer.moving_average(window, field)
        if not averages:
            print("\nNot enough data for moving average.")
            return
        if field == "weight":
            averages = [from_lbs(value, unit) for value in averages]
            print(f"\nMoving averages for weight in {unit} (window={window}):")
        else:
            print(f"\nMoving averages for {field} (window={window}):")
        print([round(val, 2) for val in averages])

    elif choice == "2":
        if len(log) == 0:
            print("\nNo entries to chart yet.")
            return
        entries = log.get_entries_list()
        trend = analyzer.trend_weights()
        print()
        print(
            render_weight_chart(
                [entry.date for entry in entries], [entry.weight for entry in entries], trend, unit, width=chart_width()
            )
        )
        print(
            f"\nLatest trend weight: {format_weight(trend[-1], unit, decimals=1)} "
            f"(scale: {format_weight(entries[-1].weight, unit, decimals=1)})"
        )
        if len(log) >= 2:
            print(f"Overall: {analyzer.weight_trend(unit)}")

    else:
        print("\nInvalid choice. Please select 1 or 2.")


def choose_unit(current: str) -> str | None:
    """Ask which unit to use; returns it, or None (after saying so) for an invalid answer."""
    answer = input(f"Show weights in 'lbs' or 'kg' (currently {current}): ").strip()
    try:
        return normalize_unit(answer)
    except ValueError:
        print(f"\nPlease choose 'lbs' or 'kg'. Still using {current}.")
        return None


def main(data_file=None, units=None) -> int:
    """Run the interactive menu. With data_file, the log is loaded from it at
    startup and saved back after every change, and the chosen weight unit is kept
    in a settings file next to it; without it nothing is persisted. `units`
    overrides the saved unit for this session. Returns the process exit status."""
    if data_file is None:
        log = CaloriesLog()
    else:
        try:
            log = load_log(data_file)
        except StorageError as e:
            # Refuse to start rather than risk overwriting the file with an empty log.
            print(f"Error: {e}", file=sys.stderr)
            print("Fix or move that file, or use --data-file to choose another one.", file=sys.stderr)
            return 1
        if len(log) == 0:
            print(f"No saved entries yet. Changes will be saved to {data_file}")
        else:
            noun = "entry" if len(log) == 1 else "entries"
            print(f"Loaded {len(log)} saved {noun} from {data_file}")

    settings_file = None if data_file is None else settings_file_for(data_file)
    settings = dict(DEFAULT_SETTINGS) if settings_file is None else load_settings(settings_file)
    unit = normalize_unit(units) if units is not None else settings["unit"]
    unsaved = False

    def save() -> bool:
        nonlocal unsaved
        if data_file is None:
            return True
        try:
            save_log(log, data_file)
        except OSError as e:
            unsaved = True
            print(
                f"Warning: could not save to {data_file}: {e}. "
                f"Changes since the last successful save are not saved yet."
            )
            return False
        unsaved = False
        return True

    def change_unit():
        nonlocal unit
        chosen = choose_unit(unit)
        if chosen is None:
            return
        unit = settings["unit"] = chosen
        print(f"\nWeights are now shown in {unit}.")
        if settings_file is None:
            return
        try:
            save_settings(settings, settings_file)
        except OSError as e:
            print(f"Warning: could not save the unit preference to {settings_file}: {e}")

    def finish():
        # Changes are saved as they are made; retry once if the last save failed.
        if unsaved and not save():
            print("Warning: unsaved changes were lost.")
        print("\nGoodbye!")

    while True:
        print("\n=== Maintenance Calorie Finder ===")
        for number, label in enumerate(MENU_OPTIONS, start=1):
            print(f"{number}. {label}")

        try:
            choice = input(f"Choose an option (1 - {EXIT_CHOICE}): ").strip()

            if choice == "1":
                # Manual entry
                date = prompt_date("Enter date (YYYY-MM-DD): ")
                weight = prompt_weight("Enter weight", unit)
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
                    entries, unitless = FileLoader.load_file_with_unit_info(filepath)
                    if unitless and unit != LBS:
                        # Plain weights default to lbs; a kg user's file may well be in kg.
                        file_unit = ask_file_unit(unitless)
                        if file_unit != LBS:
                            entries = FileLoader.load_file(filepath, default_unit=file_unit)
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
                if weight_change is None:
                    print("Weight change: N/A (need at least 2 entries)")
                else:
                    print(f"Weight change: {from_lbs(weight_change, unit):.2f} {unit}")
                if avg_calories is None:
                    print("Average calories: N/A (no entries)")
                else:
                    print(f"Average calories: {avg_calories:.0f}")

            elif choice == "4":
                # Maintenance calories
                calculator = MaintenanceCalculator(log)
                maintenance = calculator.estimate()
                if maintenance is None:
                    print("\nNot enough data to estimate maintenance calories (need at least 2 entries).")
                else:
                    print(f"\nEstimated Maintenance Calories: {maintenance:.0f} per day")

            elif choice == "5":
                # Goal planner
                calculator = MaintenanceCalculator(log)
                maintenance = calculator.estimate()
                if maintenance is None:
                    print("\nNot enough data to plan a goal yet (need at least 2 entries to estimate maintenance).")
                else:
                    current_weight = prompt_weight("Enter current weight", unit)
                    target_weight = prompt_weight("Enter target weight", unit)
                    time_frame = prompt_int("Enter time frame (days): ", minimum=1)
                    planner = GoalPlanner(current_weight, target_weight, time_frame, maintenance)
                    print(f"\nRecommended Intake (Algebraic): {planner.recommend_calories():.0f}")
                    print(f"Recommended Intake (Optimized): {planner.recommend_calories_optimized():.0f}")
                    for warning in planner.safety_warnings(unit):
                        print(f"Warning: {warning}")
                    print(f"\n{GOAL_DISCLAIMER}")

            elif choice == "6":
                # Trend analysis
                analyze_trends(log, unit)

            elif choice == "7":
                # Demo data: the bundled 20-day sample, enough for a stable estimate
                print("\nLoading demo entries...")
                demo_entries = FileLoader.load_file(str(DEMO_DATA))
                added, skipped = add_entries(log, demo_entries)
                print(
                    f"Added {added} of {len(demo_entries)} demo entries. "
                    "Try viewing summary or calculating maintenance."
                )
                print_skipped(skipped)
                if added:
                    save()

            elif choice == "8":
                list_entries(log, unit)

            elif choice == "9":
                if edit_entry(log, unit):
                    save()

            elif choice == "10":
                if delete_entry(log, unit):
                    save()

            elif choice == "11":
                export_entries(log, unit, data_file)

            elif choice == "12":
                change_unit()

            elif choice == EXIT_CHOICE:
                finish()
                break

            else:
                print(f"\nInvalid choice. Please select a number 1 - {EXIT_CHOICE}.")

        except (EOFError, KeyboardInterrupt):
            finish()
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
    return main(data_file, args.units)


if __name__ == "__main__":
    sys.exit(run())
