from scipy.optimize import minimize, minimize_scalar
from datetime import datetime, timedelta
import logging

# Configure root logger ; see info (add entry), warning -- good for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    def insert_sorted(self, data: DailyEntry):
        # Insert keeping the list sorted ascending by date, so the head is always
        # the earliest entry and the tail the latest, regardless of insertion order.
        # Entries with an equal date preserve their insertion order (stable).
        new_node = Node(data)
        if not self._head:
            self._head = new_node
            self._tail = new_node
        elif data._date < self._head._data._date:
            new_node._next = self._head
            self._head = new_node
        elif data._date >= self._tail._data._date:
            self._tail._next = new_node
            self._tail = new_node
        else:
            current = self._head
            while current._next and current._next._data._date <= data._date:
                current = current._next
            new_node._next = current._next
            current._next = new_node
        self._length += 1

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

    #pull data from DailyEntry class
    def add_entry(self, entry: DailyEntry) -> bool: 
        if EntryValidator.is_valid(entry, self._entries):
            self._entries.insert_sorted(entry)
            logging.info(f"Added entry: {entry}")
            return True
        else:
            logging.warning(f"Invalid entry: {entry}")
            return False

    # Calculate average calories using all entries (None when there is no data)
    def average_calories(self):
        if len(self._entries) == 0:
            return None
        return sum(entry._calories for entry in self._entries) / len(self._entries)

    # Calculate weight difference (start - end); None when there are fewer than 2 entries
    def weight_difference(self):
        if len(self._entries) < 2: #need a head and tail to calculate difference
            return None
        return self._entries._head._data._weight - self._entries._tail._data._weight #start weight - end weight

    # Calculate days tracked
    def days_tracked(self): 
        if len(self._entries) < 2: #need a head and tail to calculate days
            return len(self._entries)
        return (self._entries._tail._data._date - self._entries._head._data._date).days + 1

    # Allow iteration over the log
    def __iter__(self): 
        current = self._entries._head
        while current:
            yield current._data
            current = current._next
    
    # Get List of all entries
    def get_entries_list(self) -> list[DailyEntry]:
        return list(self._entries)

class MaintenanceCalculator: 
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def maintenance_calculator(self):
        avg_cals = self._log.average_calories()
        weight_diff = self._log.weight_difference()
        days = self._log.days_tracked()

        # Need at least two entries spanning a real time window to estimate maintenance.
        if avg_cals is None or weight_diff is None or days == 0:
            return None

        cals_change = weight_diff * 3500
        daily_cals_change = cals_change / days

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
    
    def weight_trend(self) -> str:
        if len(self._log._entries) < 2:
            return "Insufficient data"
        
        weight_diff = self._log.weight_difference()
        days = self._log.days_tracked()
        rate = weight_diff / days  # lbs/day; positive means losing (start - end)

        # Threshold is expressed in the same unit as the reported rate (lbs/day).
        if abs(rate) < 0.05:
            return f"Stable weight (~{abs(rate):.2f} lbs/day over {days} days)"
        elif weight_diff > 0:
            return f"Losing weight: {abs(rate):.2f} lbs/day average"
        else:
            return f"Gaining weight: {abs(rate):.2f} lbs/day average"
    
class EntryValidator:
    @staticmethod
    def is_valid(entry:DailyEntry, existing_entries: LinkedList = None) -> bool:
        if not (800 <= entry._calories <= 5000):
            logging.warning(f'Calories are out of range: {entry._calories}')
            return False
        
        if not (50 <= entry._weight <= 600):
            logging.warning(f'Weight is out of range: {entry._weight}')
            return False
        
        if not isinstance(entry._date, datetime):
            logging.warning(f'Date is not a datetime object: {entry._date}')
            return False
        
        if existing_entries and len(existing_entries) > 0:
            last_entry = existing_entries._tail._data
            weight_change = abs(entry._weight - last_entry._weight)
            days_diff = (entry._date - last_entry._date).days

            if days_diff == 1 and weight_change > 5:
                logging.warning(f'Weight change too large for consecutive days: {entry._weight:.1f} lbs in 1 day')
                return False
        
        return True

class GoalPlanner:
    def __init__ (self, current_weight: float, target_weight: float, time_frame: int, maintenance_calories: float):
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
                # daily_balance > 0 is a surplus (eating above maintenance),
                # daily_balance < 0 is a deficit (eating below maintenance).
                daily_balance = calories - maintenance
                weight += daily_balance / 3500

                # Adjust maintenance based on weight change (metabolic adaptation):
                # it drifts down as you lose weight and up as you gain.
                weight_change_factor = abs(weight - self._current_weight)

                if daily_balance < 0:  # deficit -> losing weight -> lower maintenance
                    maintenance -= 5 * weight_change_factor
                elif daily_balance > 0:  # surplus -> gaining weight -> higher maintenance
                    maintenance += 5 * weight_change_factor

            return (weight - self._target_weight) ** 2  # Minimize the squared difference

        result = minimize_scalar(objective, bounds=(800, 5000), method='bounded') # realistic calorie bounds
        if not result.success:
            logging.warning(f"Optimization did not converge: {result.message}")
        return result.x