from scipy.optimize import minimize_scalar
from datetime import datetime
import logging
import numbers
import statistics

# Configure root logger ; see info (add entry), warning -- good for debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Energy content of one pound of body weight (standard approximation).
KCAL_PER_LB = 3500

# Metabolic adaptation used by GoalPlanner.recommend_calories_optimized:
# maintenance shifts by this many kcal/day per lb of weight lost (or gained)
# relative to the starting weight.
ADAPT_KCAL_PER_LB = 10

# Largest plausible change in body weight per day between two weigh-ins; a
# bigger swing is almost certainly a typo or a unit mix-up.
MAX_LBS_PER_DAY = 5

# How far (lbs) the optimized plan may miss the target before it is reported
# as unreachable within GoalPlanner.CALORIE_BOUNDS.
UNREACHABLE_TOLERANCE_LBS = 0.1

class DailyEntry:
    def __init__(self, date: datetime, weight: float, calories: int):
        if not isinstance(date, datetime):
            raise TypeError("Date must be a datetime object")
        # bool is a subclass of int, but True/False is never a real measurement
        if isinstance(weight, bool) or not isinstance(weight, numbers.Real):
            raise TypeError(f"Weight must be a number, got {weight!r}")
        if isinstance(calories, bool) or not isinstance(calories, numbers.Integral):
            raise TypeError(f"Calories must be a whole number, got {calories!r}")
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
        return f"DailyEntry({self._date.strftime('%Y-%m-%d')}, {self._weight}lbs, {self._calories}cals)"

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
        elif data.date < self._head._data.date:
            new_node._next = self._head
            self._head = new_node
        elif data.date >= self._tail._data.date:
            self._tail._next = new_node
            self._tail = new_node
        else:
            current = self._head
            while current._next and current._next._data.date <= data.date:
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

    @property
    def first(self) -> DailyEntry:
        return self._head._data if self._head else None

    @property
    def last(self) -> DailyEntry:
        return self._tail._data if self._tail else None

class CaloriesLog:
    def __init__(self):
        self._entries = LinkedList()
        self._dates = set()  # calendar days already logged, for duplicate detection

    #pull data from DailyEntry class
    def add_entry(self, entry: DailyEntry) -> bool: 
        # One entry per calendar day; a second one would skew every estimate.
        if entry.date.date() in self._dates:
            logging.warning(f"Duplicate date, entry rejected: {entry}")
            return False
        if EntryValidator.is_valid(entry, self._entries):
            self._entries.insert_sorted(entry)
            self._dates.add(entry.date.date())
            logging.info(f"Added entry: {entry}")
            return True
        else:
            logging.warning(f"Invalid entry: {entry}")
            return False

    # Calculate average calories using all entries (None when there is no data)
    def average_calories(self):
        if len(self._entries) == 0:
            return None
        return sum(entry.calories for entry in self._entries) / len(self._entries)

    # Calculate weight difference (start - end); None when there are fewer than 2 entries
    def weight_difference(self):
        if len(self._entries) < 2: #need a head and tail to calculate difference
            return None
        return self._entries.first.weight - self._entries.last.weight #start weight - end weight

    # Calculate days tracked
    def days_tracked(self):
        if len(self._entries) < 2: #need a head and tail to calculate days
            return len(self._entries)
        return (self._entries.last.date - self._entries.first.date).days + 1

    # Least-squares slope of weight vs. day offset, in lbs/day (positive = gaining).
    # Uses every weigh-in, so one noisy reading can't dominate the estimate.
    # None when there are fewer than 2 distinct dates.
    def weight_slope(self):
        if len(self._entries) < 2:
            return None
        start = self._entries.first.date.date()
        days = [(entry.date.date() - start).days for entry in self._entries]
        if len(set(days)) < 2:
            return None
        weights = [entry.weight for entry in self._entries]
        return statistics.linear_regression(days, weights).slope

    # First (earliest) and last (latest) entries, or None when the log is empty
    def first(self) -> DailyEntry:
        return self._entries.first

    def last(self) -> DailyEntry:
        return self._entries.last

    def __len__(self) -> int:
        return len(self._entries)

    # Allow iteration over the log
    def __iter__(self):
        yield from self._entries

    # Get List of all entries
    def get_entries_list(self) -> list[DailyEntry]:
        return list(self._entries)

class MaintenanceCalculator: 
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def maintenance_calculator(self):
        avg_cals = self._log.average_calories()
        slope = self._log.weight_slope()

        # Need at least two distinct dates to estimate maintenance.
        if avg_cals is None or slope is None:
            return None

        # Gaining (slope > 0) means intake was above maintenance, and vice versa.
        return avg_cals - slope * KCAL_PER_LB
    
class TrendAnalyzer:
    def __init__ (self, log:CaloriesLog):
        self._log = log

    def moving_average(self, window_size, field = "calories"):
        if field not in ("calories", "weight"):
            raise ValueError("Field must be 'calories' or 'weight'")
        
        if field == "calories":
            values = [entry.calories for entry in self._log]
        else:
            values = [entry.weight for entry in self._log]

        if len(values) < window_size or window_size <= 0: # Check if the window size is valid
            return []
        
        moving_averages = []

        for i in range (len(values) - window_size + 1): # Iterate through the list
            window = values [i:i + window_size] # Get the current window
            average = sum(window) / window_size
            moving_averages.append(average)

        return moving_averages
    
    def weight_trend(self) -> str:
        rate = self._log.weight_slope()  # lbs/day; positive means gaining
        if rate is None:
            return "Insufficient data"
        days = self._log.days_tracked()

        # Threshold is expressed in the same unit as the reported rate (lbs/day).
        if abs(rate) < 0.05:
            return f"Stable weight (~{abs(rate):.2f} lbs/day over {days} days)"
        elif rate < 0:
            return f"Losing weight: {abs(rate):.2f} lbs/day average"
        else:
            return f"Gaining weight: {abs(rate):.2f} lbs/day average"
    
class EntryValidator:
    @staticmethod
    def is_valid(entry:DailyEntry, existing_entries: LinkedList = None) -> bool:
        if not (800 <= entry.calories <= 5000):
            logging.warning(f'Calories are out of range: {entry.calories}')
            return False

        if not (50 <= entry.weight <= 600):
            logging.warning(f'Weight is out of range: {entry.weight}')
            return False

        if not isinstance(entry.date, datetime):
            logging.warning(f'Date is not a datetime object: {entry.date}')
            return False

        # Compare against the chronological neighbours rather than only the latest
        # entry, so back-filled days are checked too. The allowed change scales
        # with the number of days between the two weigh-ins.
        day = entry.date.date()
        before = after = None
        for existing in existing_entries or ():
            if existing.date.date() <= day:
                before = existing
            else:
                after = existing
                break

        for neighbour in (before, after):
            if neighbour is None:
                continue
            day_gap = max(abs((day - neighbour.date.date()).days), 1)
            weight_change = abs(entry.weight - neighbour.weight)
            if weight_change > MAX_LBS_PER_DAY * day_gap:
                logging.warning(f'Weight change too large: {weight_change:.1f} lbs over {day_gap} day(s)')
                return False

        return True

class GoalPlanner:
    CALORIE_BOUNDS = (800, 5000)  # realistic daily intake range for recommendations

    def __init__ (self, current_weight: float, target_weight: float, time_frame: int, maintenance_calories: float):
        # bool is an int subclass but never a meaningful number of days
        if isinstance(time_frame, bool) or not isinstance(time_frame, int):
            raise TypeError(f"Time frame must be a whole number of days, got {time_frame!r}")
        if time_frame <= 0:
            raise ValueError(f"Time frame must be a positive number of days, got {time_frame}")
        self._current_weight = current_weight
        self._target_weight = target_weight
        self._time_frame = time_frame
        self._maintenance = maintenance_calories

    def recommend_calories(self):
        weight_diff = self._target_weight - self._current_weight
        total_calories = weight_diff * KCAL_PER_LB
        daily_calories = total_calories / self._time_frame
        
        return self._maintenance + daily_calories
    
    def recommend_calories_optimized(self):
        def objective(calories):
            weight = self._current_weight

            for _ in range(self._time_frame):
                # Metabolic adaptation: maintenance tracks total weight change so far
                # (lower after losing, higher after gaining). It is recomputed from the
                # starting value each day rather than accumulated, so it doesn't compound.
                maintenance = self._maintenance - ADAPT_KCAL_PER_LB * (self._current_weight - weight)
                weight += (calories - maintenance) / KCAL_PER_LB

            return (weight - self._target_weight) ** 2  # Minimize the squared difference

        low, high = self.CALORIE_BOUNDS
        result = minimize_scalar(objective, bounds=(low, high), method='bounded')
        if not result.success:
            logging.warning(f"Optimization did not converge: {result.message}")
        # result.fun is the squared miss in lbs; a reachable target is hit almost exactly,
        # so a real miss means the optimum is held back by a calorie bound.
        if result.fun > UNREACHABLE_TOLERANCE_LBS ** 2:
            logging.warning(
                f"Target of {self._target_weight} lbs in {self._time_frame} days is not reachable "
                f"within {low}-{high} kcal/day; recommendation is pinned at the bound"
            )
        return float(result.x)
