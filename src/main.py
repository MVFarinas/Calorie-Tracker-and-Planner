#This program is a modification of the original source code to utilize DSAs 
#This version will utiilize Linked Lists, allow for moving averages, data validation, and file persistence

class DailyEntry:
    def __init__(self, date, weight, calories):
        self._date = date
        self._weight = weight
        self._calories = calories

class CaloriesLog:
    def __init__(self):
        self._entries = [] #initiate empty list

    def add_entry(self, entry: DailyEntry): #pull data from DailyEntry class
        self._entries.append(entry)

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

class MaintenanceEstimator:
    def __init__(self):
        {}

class GoalPlanner:
    def __init__(self):
        {}