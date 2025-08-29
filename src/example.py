from entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner, EntryValidator, TrendAnalyzer
from datetime import datetime

'''
Example Data
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

    print(f"Average calories: {avg_cals:.0f} calories")
    print(f"Weight difference: {weight_diff:.2f} lbs")
    print(f"Days tracked: {days_tracked:.0f} days")
    print(f"Maintenance Calories: {maintenance:.0f} calories per day")

    trend = TrendAnalyzer(log)
    window_size = 3
    calorie_trend = trend.moving_average(window_size)
    print(f"\n--- Moving Average (calories, window = {window_size}) ---")
    for i, avg in enumerate(calorie_trend, start=window_size):
        print(f"Day {i}: {avg:.0f} cal")

    planner = GoalPlanner(
        current_weight = 197.4,
        target_weight = 215,
        time_frame = 90, 
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    intake_optimization = planner.recommend_calories_optimized()
    print(f'\nYour Recommended Daily Caloric Intake (algebra): {intake_reccomendation:.0f} calories/day')
    print(f'The Optimized Daily Caloric Intake (nonlinear): {intake_optimization:.0f} calories/day\n')
