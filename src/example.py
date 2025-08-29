from entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, EntryValidator, TrendAnalyzer
from datetime import datetime

'''
A quick demo script to showcase the functionality of the CaloriesLog, MaintenanceCalculator, TrendAnalyzer, and GoalPlanner classes.
'''

if __name__ == "__main__":
    log = CaloriesLog()

    # Example: add entries, but validate each one before inserting
    raw_entries = [
        DailyEntry(datetime(2025, 7, 1), weight=200, calories=2200),
        DailyEntry(datetime(2025, 7, 2), weight=198.8, calories=2200),
        DailyEntry(datetime(2025, 7, 3), weight=198.2, calories=2150),
        DailyEntry(datetime(2025, 7, 4), weight=197.9, calories=2100),
        DailyEntry(datetime(2025, 7, 5), weight=197.7, calories=2100),
        DailyEntry(datetime(2025, 7, 6), weight=197.6, calories=2050),
        DailyEntry(datetime(2025, 7, 7), weight=197.5, calories=2050),
        DailyEntry(datetime(2025, 7, 8), weight=197.5, calories=2050),
        DailyEntry(datetime(2025, 7, 9), weight=197.4, calories=2000),
        DailyEntry(datetime(2025, 7, 10), weight=197.4, calories=2000),
        DailyEntry(datetime(2025, 7, 11), weight=197.1, calories=2200),
        DailyEntry(datetime(2025, 7, 12), weight=197.0, calories=2200),
        DailyEntry(datetime(2025, 7, 13), weight=197.0, calories=2200),
        DailyEntry(datetime(2025, 7, 14), weight=197.0, calories=2200),
        DailyEntry(datetime(2025, 7, 15), weight=196.9, calories=2200),
        DailyEntry(datetime(2025, 7, 16), weight=196.9, calories=2200),
        DailyEntry(datetime(2025, 7, 17), weight=196.8, calories=2200),
        DailyEntry(datetime(2025, 7, 18), weight=196.8, calories=2200),
        DailyEntry(datetime(2025, 7, 19), weight=196.8, calories=2200),
        DailyEntry(datetime(2025, 7, 20), weight=196.8, calories=2200),
    ]

    print("\n--- Loading entries ---")
    for entry in raw_entries:
        if EntryValidator.is_valid(entry):
            log.add_entry(entry)
        else:
            print(f"Invalid entry skipped: {entry._date}, {entry._weight} lbs, {entry._calories} cal")

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
        current_weight = log.get_entries_list()[-1]._weight,
        target_weight = 215,
        time_frame = 30, 
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    intake_optimization = planner.recommend_calories_optimized()
    print(f'\n--- Goal Planning ---')
    print(f'To achieve a weight of {planner._target_weight} lbs in {planner._time_frame} days:')
    print(f'Your Recommended Daily Caloric Intake (Algebraic): {intake_reccomendation:.0f} calories/day')
    print(f'Your Optimized Daily Caloric Intake (Nonlinear): {intake_optimization:.0f} calories/day\n')
