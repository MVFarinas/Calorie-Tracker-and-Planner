#This program is a modification of the original source code to utilize DSAs 
#This version will utiilize Linked Lists, allow for moving averages, data validation, and file persistence

class DailyEntry:
    def __init__(self, date, weight, calories):
        self._date = date
        self._calories = calories
        self._weight = weight

class Node:
    def __init__(self, data:DailyEntry):
        self._data = data
        self._next = None

class LinkedList:
    def __init__(self):
        self._head = None
        self._length = 0

    def append (self, data:DailyEntry):
        new_node = Node(data)
        if not self._head:
            self._head = new_node

        else:
            current = self._head

            while current._next:
                current = current._next
            current._next = new_node

        self._length +=1

    def __iter__(self):
        current = self._head
        while current:
            yield current._data
            current = current._next

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
    