from pathlib import Path
from datetime import datetime
import logging
from .entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, TrendAnalyzer
from .util.file_loader import FileLoader

DATA_DIR = Path(__file__).parent / "data"

'''
A quick demo script to showcase the functionality of the CaloriesLog, MaintenanceCalculator, TrendAnalyzer, and GoalPlanner classes.
'''

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    log = CaloriesLog()

    print(f'\n--- File Loading Demo ---')
    #Swap between different file formats for testing
    entries = FileLoader.load_file(str(DATA_DIR / "sample_data.csv"))
    #entries = FileLoader.load_file(str(DATA_DIR / "sample_data.json"))

    print("\n--- Loading entries ---")
    added = sum(1 for entry in entries if log.add_entry(entry))
    print(f"\nLoaded {added} of {len(entries)} entries")
    print(f"Average Daily Calories: {log.average_calories():.0f}\n")
    print(f'--- End File Loading Demo ---')

    # Example: add_entry validates each entry and returns False when it is rejected.
    # Each of these fails a different check, so the log above is left unchanged.
    invalid_entries = [
        DailyEntry(datetime(2025, 7, 20), weight=196.8, calories=2200),  # date already logged
        DailyEntry(datetime(2025, 7, 21), weight=196.7, calories=300),   # calories out of range
        DailyEntry(datetime(2025, 7, 21), weight=203.5, calories=2200),  # >5 lb swing in one day
    ]
    print(f'\n--- Quick Demo: Adding Entries with Validation ---')
    for entry in invalid_entries:
        if not log.add_entry(entry):
            print(f"Invalid entry skipped: {entry}")

    calculator = MaintenanceCalculator(log)
    maintenance = calculator.maintenance_calculator()
    avg_cals = log.average_calories()
    weight_diff = log.weight_difference()
    days_tracked = log.days_tracked()
    analyzer = TrendAnalyzer(log)

    print("\n--- Quick Demo Results ---")
    print(f"Average calories: {avg_cals:.0f} calories")
    print(f"Weight difference: {weight_diff:.2f} lbs")
    print(f"Days tracked: {days_tracked:.0f} days")
    print(f"Maintenance Estimate: {maintenance:.0f} calories per day")
    print(f"Weight trend: {analyzer.weight_trend()}")

    planner = GoalPlanner(
        current_weight = log.last().weight,
        target_weight = 190,
        time_frame = 60,
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    intake_optimization = planner.recommend_calories_optimized()
    print(f'\n--- Goal Planning ---')
    print(f'To achieve a weight of {planner._target_weight} lbs in {planner._time_frame} days:')
    print(f'Your Recommended Daily Caloric Intake (Algebraic): {intake_reccomendation:.0f} calories/day')
    print(f'Your Optimized Daily Caloric Intake (Nonlinear): {intake_optimization:.0f} calories/day')
    for warning in planner.safety_warnings():
        print(f'Warning: {warning}')
    print('(Estimates only, not medical advice.)\n')