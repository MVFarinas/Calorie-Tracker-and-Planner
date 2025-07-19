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
        {}

class MaintenanceEstimator:
    def __init__(self):
        {}

class GoalPlanner:
    def __init__(self):
        {}