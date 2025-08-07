#This program is a modification of the original source code to utilize DSAs 
#This version will utiilize Linked Lists, allow for moving averages, data validation, and file persistence

from scipy.optimize import minimize, minimize_scalar
from datetime import datetime, timedelta

class DailyEntry:
    def __init__(self, date, weight, calories):
        self._date = date
        self._weight = weight
        self._calories = calories

class Node:
    def __init__(self, data:DailyEntry):
        self._data = data
        self._next = None

class LinkedList:
    def __init__(self):
        self._head = None
        self._tail = None
        self._length = 0 

    def append (self, data:DailyEntry):
        new_node = Node(data)
        if not self._head: # If the list is empty, set the new node as both head and tail
            self._head = new_node
            self._tail = new_node

        else:
            self._tail.next = new_node # Link the new node to the end of the list
            self._tail = new_node # Update the tail to the new node
        self._length +=1

    def __iter__(self): 
        current = self._head
        while current:
            yield current._data
            current = current._next

class CaloriesLog:
    def __init__(self):
        self._entries = LinkedList()

    def add_entry(self, entry: DailyEntry): #pull data from DailyEntry class
        self._entries.append(entry)

    def average_calories(self):
        if self._entries._length == 0:
            return 0
        return sum(entry._calories for entry in self._entries) / self._entries._length
    
    def weight_difference(self):
        if self._entries._length < 2: #need a head and tail to calculate difference
            return 0
        return self._entries._tail._data._weight - self._entries._head._data._weight
    
    def days_tracked(self):
        if self._entries._length < 2: #need a head and tail to calculate days
            return 0
        return (self._entries._tail._data._date - self._entries._head._data._date).days + 1

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
    
class TrendAnalyzer:
    def __init__ (self, entries:DailyEntry):
        self._entries = entries

    def moving_average(self, window_size):
        values = [entry._calories for entry in self._entries]
        if len(values) < window_size:
            return []
        
        moving_averages = []
        for i in range (len(values) - window_size + 1): # Iterate through the list
            window = values [i:i + window_size] # Get the current window
            average = sum(window) / window_size
            moving_averages.append(average)

        return moving_averages
    
class EntryValidator:
    @staticmethod
    def is_valid(entry:DailyEntry) -> bool:
        return 800 <= entry._calories <= 6000 and 50 <= entry._weight <= 600
    
class GoalPlanner:
    def __init__ (self, current_weight, target_weight, time_frame, maintenance_calories):
        self._current_weight = current_weight
        self._target_weight = target_weight
        self._time_frame = time_frame
        self._maintenance = maintenance_calories

    def recommend_calories(self):
        weight_diff = self._target_weight - self._current_weight
        total_calories = weight_diff * 3500
        daily_calories = total_calories / self._time_frame
        
        return self._maintenance + daily_calories
    
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

    print(f'Maintenance Calories: {maintenance:.2f} calories per day')

    planner = GoalPlanner(
        current_weight = 178.5,
        target_weight = 175,
        time_frame = 30, 
        maintenance_calories = maintenance
    )

    intake_reccomendation = planner.recommend_calories()
    print(f'Your Recommended Daily Caloric Intake should be: {intake_reccomendation:.0f} calories per day')