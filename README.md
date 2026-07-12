# Calorie Tracker and Planner
A Python project that helps users estimate their maintenance calories(TDEE) based on tracked caloric intake and body weight over time instead of algebraic calculations based on weight and height.

The project supports importing data from `.csv` and `.json`, performs analysis with custom data structures, and even applies nonlinear optimization (sciPy minimize_scalar) to provide more realistic caloric recommendations when reverse engineering calories for a goal weight.

# Features
- Custom Data Structures with Object Oriented Programming:

  - LinkedList -> implementation for storing daily entries
  - DailyEntry, CaloriesLog, MaintenanceCalculator Classes

- Trend Analysis

  - Moving averages of weight or calories with TrendAnalyzer Class

- Validation:

  - Ensures realistic entries (`EntryValidator`)

- Caloric Recommendations:

  - Algebraic approach (linear math)
  - Optimized approach using scipy.optimize (nonlinear metabolic adaptation model)

- File Import (read-only):
  - Import data from `.csv`, `.json`, and `.txt` files using `file_loader.py`

# Requirements
- Python3
- SciPy

Install dependencies with:
```
pip install -r requirements.txt
```

# Usage
Run both entry points as modules from the repository root:

- `python -m src.example` runs a demo of the methods in `entry.py` and the file loading in `file_loader.py`
- `python -m src.main` launches the CLI to input user data, load file data, and analyze it

# Why I'm Doing This Project
I wanted to combine my interest in fitness and nutrition with my growing skills in software engineering. Many commercial fitness apps are closed-source so users never see how calculations are made. 

This project also explicitly models how recommended calorie consumption changes in non-linear situations, such as the metabolic adjustments that occur during weight loss or weight gain phases.

# Goal
This project is my way to:
- Practice object-oriented programming and custom data structures  
- Apply scientific and mathematical concepts (calorie balance, optimization) in code  
- Build a practical tool that can help me and others understand nutrition data better
