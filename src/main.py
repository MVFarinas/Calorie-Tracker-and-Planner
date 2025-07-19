#This program is a modification of the original source code to utilize DSAs 
#This version will utiilize Linked Lists, allow for moving averages, data validation, and file persistence

class DailyEntry:
    def __init__(self, date, weight, calories):
        self._date = date
        self._calories = calories
        self._weight = weight

class CaloriesLog:
    def __init__(self):
        self._entries = [] #initiate empty list

    def add_entry(self, entry: DailyEntry): #pull data from DailyEntry class
        self._entries.append(entry)

    def average_calories(self):
        total_cals = sum(self._entries.calories)
        avg_cals = total_cals / len(self._entries.calories)
        return avg_cals
    
    def weight_difference(self):
        start_weight = self._entries.weight[0]
        final_weight = self._entries.weight[-1]
        weight_diff = final_weight - start_weight
        return weight_diff
    
    def days_tracked(self):
        first_day = self._entries.date[0]
        last_day = self._entries.date[-1]
        total_days = last_day - first_day + 1
        return total_days

class MaintenanceCalculator:
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def maintenance_calculator(self):
        avg_cals = self._log.average_calories()
        weight_diff = self._log.weight_difference()

        cals_change = weight_diff * 3500
        daily_cals_change = cals_change / self._log.days_tracked()
        
        maintenance = avg_cals - daily_cals_change
        return maintenance

class GoalPlanner:
    def __init__(self):
        {}