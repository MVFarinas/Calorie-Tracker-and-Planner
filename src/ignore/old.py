# This project will take a person's calorie intake + weight as well as their 
# weight goals and find their maintenance calories and suggest a plan
# to meet their weight goals

# Helpfer function that gets goals and caloric intake over the course of 1-2 weeks
def get_goal():
    goal = input ("Do you want to gain, lose, or maintain your weight (G or L or M): ")
    goal = goal.upper()
    while goal != "G" and goal != "L" and goal != "M":
        goal = input ("Please input a weight goal (G, L, M): ")
        goal = goal.upper()
    return goal

def get_weight():
    weight = input ("Starting weight in lbs: ")
    return weight

def get_duration():
    while True:
        duration = input("How many data points would you like to consider (2 to 14)? ")
        if duration.isdigit():
            duration = int(duration)
            if 2 <= duration <= 14:
                return duration
            else:
                print("Please enter a number between 2 and 14")
        else:
            print("Invalid input. Please enter a whole number")

def calorie_list(duration):
    cal_list = []
    while len(cal_list) < duration:
        calories = input("Please enter your daily caloric intake for this data point: ")
        if calories.isdigit():
            calories = int(calories)
            cal_list.append(calories)
        else:
            print("Please enter a whole number")
    return cal_list

def weight_list(duration):
    weight_list = []
    while len(weight_list) < duration:
        weight = input("Please enter your daily weight for this data point: ")
        if weight.isdigit():
            weight = int(weight)
            weight_list.append(weight)
        else:
            print("Please enter a whole number in lbs")
    return weight_list