from entry import CaloriesLog, DailyEntry, MaintenanceCalculator, GoalPlanner
from datetime import datetime

'''
Example Data
'''

if __name__ == "__main__":
    log = CaloriesLog()
    # Early days: bigger drops (water + glycogen loss)
    log.add_entry(DailyEntry(datetime(2025, 7, 1), weight = 200, calories =2200))        
    log.add_entry(DailyEntry(datetime(2025, 7, 2), weight = 198.8, calories =2200))
    log.add_entry(DailyEntry(datetime(2025, 7, 3), weight = 198.2, calories =2150))
    log.add_entry(DailyEntry(datetime(2025, 7, 4), weight = 197.9, calories =2100))
    
    # Then: slower losses
    log.add_entry(DailyEntry(datetime(2025, 7, 5), weight = 197.7, calories =2100))
    log.add_entry(DailyEntry(datetime(2025, 7, 6), weight = 197.6, calories =2050))
    log.add_entry(DailyEntry(datetime(2025, 7, 7), weight = 197.5, calories =2050))
    log.add_entry(DailyEntry(datetime(2025, 7, 8), weight = 197.5, calories =2050))
    log.add_entry(DailyEntry(datetime(2025, 7, 9), weight = 197.4, calories =2000))
    log.add_entry(DailyEntry(datetime(2025, 7, 10), weight = 197.4, calories =2000))

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
        current_weight = 197.4,
        target_weight = 190,
        time_frame = 30, 
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    intake_optimization = planner.recommend_calories_optimized()
    print(f'Your Recommended Daily Caloric Intake (algebra): {intake_reccomendation:.0f} calories/day')
    print(f'The Optimized Daily Caloric Intake (nonlinear): {intake_optimization:.0f} calories/day')
