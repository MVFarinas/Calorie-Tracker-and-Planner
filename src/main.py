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
        weight_change = final_weight - start_weight
        return weight_change
    
    def days_tracked(self):
        first_day = self._entries.date[0]
        last_day = self._entries.date[-1]
        total_days = last_day - first_day + 1

class MaintenanceEstimator:
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def average_calories(self):
    #entry list based
        return None

    def final_weight(self):
        #entry list based
        return None
    
    def change_calories(self):
        #(start weight - final weight) * 3500
        return None
    
    def average_change_calories(self):
        #change calories / duration in days
        return None
    
    def calculate_maintenance(self):
        #cal_average + average_change_calories
        return None

class GoalPlanner:
    def __init__(self):
        {}