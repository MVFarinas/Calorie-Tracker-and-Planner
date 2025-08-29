from scipy.optimize import minimize, minimize_scalar
from datetime import datetime, timedelta

class DailyEntry:
    def __init__(self, date: datetime, weight: float, calories: int):
        if not isinstance(date, datetime):
            raise TypeError("Date must be a datetime object")
        self._date = date
        self._weight = weight
        self._calories = calories

    #introduce property decorators for getter method
    @property
    def date(self):
        return self._date

    @property
    def weight(self):
        return self._weight

    @property
    def calories(self):
        return self._calories
    
    def __str__(self) -> str:
        return f'DailyEntry({self._date.strftime('%Y-%m-%d')}, {self._weight}lbs, {self._calories}cals)'

class Node:
    def __init__(self, data: DailyEntry):
        self._data = data
        self._next = None

class LinkedList:
    def __init__(self):
        self._head = None
        self._tail = None
        self._length = 0 

    def append (self, data:DailyEntry):
        new_node = Node(data)
        # If the list is empty, set the new node as both head and tail
        if not self._head: 
            self._head = new_node
            self._tail = new_node

        else:
            self._tail._next = new_node # Link the new node to the end of the list
            self._tail = new_node # Update the tail to the new node
        self._length +=1

    def __iter__(self): 
        current = self._head
        while current:
            yield current._data
            current = current._next

    def __len__(self) -> int:
        return self._length


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
        return self._entries._head._data._weight - self._entries._tail._data._weight #start weight - end weight
    
    def days_tracked(self):
        if self._entries._length < 2: #need a head and tail to calculate days
            return 0
        return (self._entries._tail._data._date - self._entries._head._data._date).days + 1

    def __iter__(self): # allow iteration over the log
        current = self._entries._head
        while current:
            yield current._data
            current = current._next

class MaintenanceCalculator:
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def maintenance_calculator(self):
        avg_cals = self._log.average_calories()
        weight_diff = self._log.weight_difference()

        cals_change = weight_diff * 3500
        daily_cals_change = cals_change / self._log.days_tracked()
        
        maintenance = avg_cals + daily_cals_change
        return maintenance
    
class TrendAnalyzer:
    def __init__ (self, log:CaloriesLog):
        self._log = log

    def moving_average(self, window_size, field = "calories"):
        if field not in ("calories", "weight"):
            raise ValueError("Field must be 'calories' or 'weight'")
        
        if field == "calories":
            values = [entry._calories for entry in self._log]
        else:
            values = [entry._weight for entry in self._log]

        if len(values) < window_size or window_size <= 0: # Check if the window size is valid
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
    
    def recommend_calories_optimized(self):
        def objective(calories):
            weight = self._current_weight
            maintenance = self._maintenance
            time_frame = self._time_frame

            for day in range(time_frame):
                daily_deficit = calories - maintenance
                weight += daily_deficit / 3500
                
                #adjust maintenance slightly based on weight change
                if daily_deficit < 0:
                    maintenance -= 5 * (abs(weight - self._current_weight))
                elif daily_deficit > 0:
                    maintenance += 5 * (abs(weight - self._current_weight))
                                        

            return (weight - self._target_weight) ** 2  # Minimize the squared difference

        result = minimize_scalar(objective, bounds=(800, 5000), method='bounded') # realistic calorie bounds
        return result.x
            
    # To do:
    # 1. Fix JSON and CSV data (Downloads)
        # fix file_loader and entry import
    # 2. Entry Validator - ensure entry._date is datetime and check weight change for consecutive days (reject large jumps)
    # 3. Write unit tests for each class and method - particularly TrengAnalyzer and GoalPlanner
    # 4. Add documentation and comments for clarity
    # 5. Create a user interface for easier interaction (CLI or GUI)