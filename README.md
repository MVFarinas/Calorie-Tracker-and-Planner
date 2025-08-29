# Maintenance Calorie Finder

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

- File Persistence:
  - Import data from `.csv`, `.json`, and `.txt` files using `file_loader.py`

# Requirements

- Python3
- scipy

# Usage

- navigate to src/example.py to demonstrate the methods created in entry.py as well as the file persistence from file_loader.py
