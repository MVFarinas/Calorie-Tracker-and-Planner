from entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner
from datetime import datetime

'''
Example Data
'''

if __name__ == "__main__":
    log = CaloriesLog()
    log.add_entry(DailyEntry(datetime(2025, 7, 1), weight = 180, calories =2500))        
    log.add_entry(DailyEntry(datetime(2025, 7, 2), weight = 179.8, calories =2400))
    log.add_entry(DailyEntry(datetime(2025, 7, 3), weight = 179.5, calories =2400))
    log.add_entry(DailyEntry(datetime(2025, 7, 4), weight = 179, calories =2200))
    log.add_entry(DailyEntry(datetime(2025, 7, 5), weight = 178.7, calories =2300))
    log.add_entry(DailyEntry(datetime(2025, 7, 6), weight = 178.5, calories =2200))

    calculator = MaintenanceCalculator(log)
    maintenance = calculator.maintenance_calculator()
    avg_cals = log.average_calories()
    weight_diff = log.weight_difference()
    days_tracked = log.days_tracked()

    print(f"Average calories: {avg_cals:.0f} calories")
    print(f"Weight difference: {weight_diff:.2f} lbs")
    print(f"Days tracked: {days_tracked:.0f} days")
    print(f"Maintenance Calories: {maintenance:.0f} calories per day")

    planner = GoalPlanner(
        current_weight = 178.5,
        target_weight = 175,
        time_frame = 30, 
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    intake_optimization = planner.recommend_calories_optimized()
    print(f'Your Recommended Daily Caloric Intake should be: {intake_reccomendation:.0f} calories per day')
    print(f'The Optimized Daily Caloric Intake should be: {intake_optimization:.0f} calories per day')