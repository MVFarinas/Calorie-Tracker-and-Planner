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
  - Rejects a second entry for a date that is already logged
  - Rejects weight changes of more than 5 lbs per day compared with the entries just before and after the new date (so back-filled days are checked too)
  - The CLI says why an entry was rejected (e.g. duplicate date, calories out of range), and how many rows of a file were skipped for each reason

- Caloric Recommendations:

  - Algebraic approach (linear math)
  - Optimized approach using scipy.optimize (nonlinear metabolic adaptation model)
  - Safety guardrails: recommendations stay between 1200 and 5000 kcal/day, and goals that need more than 2 lbs/week of loss (or intake outside that range) are flagged with the shortest safe time frame

- File Import (read-only):
  - Import data from `.csv`, `.json`, and `.txt` files using `file_loader.py`

- Saved Between Sessions:
  - The CLI saves your log after every change and loads it again on startup (see [Your Data](#your-data))
  - List, edit (re-validated against the other entries) and delete (with confirmation) entries by date

# How the Estimates Work
- **Maintenance calories** (`MaintenanceCalculator`): fits a least-squares line through every weigh-in (weight vs. day) to get the rate of weight change in lbs/day, then
  `maintenance = average calories - slope * 3500` (about 3500 kcal per lb of body weight). Using every weigh-in instead of only the first and last keeps a single noisy reading (e.g. water weight) from dominating. At least two different dates are needed. The weight trend in `TrendAnalyzer` uses the same slope.
- **Algebraic recommendation**: `maintenance + (target - current) * 3500 / days`, i.e. a constant deficit or surplus.
- **Optimized recommendation** (metabolic adaptation): simulates the plan day by day, with maintenance shifting by `ADAPT_KCAL_PER_LB` (10 kcal/day) for every lb lost or gained relative to the starting weight, and uses `scipy.optimize.minimize_scalar` to find the constant daily intake (1200 to 5000 kcal) that lands on the target weight. For losing weight it is slightly below the algebraic value, and for gaining slightly above. If the target can't be reached within those bounds (the best plan misses it by more than 0.1 lb), the bound is returned (and the goal is flagged by the safety guardrails below).
- **Safety guardrails** (`GoalPlanner.safety_warnings`): both recommendations stay within `GoalPlanner.CALORIE_BOUNDS`, whose floor is `MIN_SAFE_CALORIES` (1200 kcal/day) and whose cap is 5000 kcal/day. A goal is flagged when it needs more than `MAX_SAFE_LBS_PER_WEEK` (2 lbs/week) of loss or would need intake outside those bounds, and the warning includes the shortest time frame that avoids all of these limits (`GoalPlanner.min_safe_time_frame`). The CLI prints these warnings with every goal plan.

> **Disclaimer:** all numbers from this project are estimates only, not medical advice. Talk to a doctor or registered dietitian before making significant changes to your diet, especially if you are pregnant, have a medical condition, or are under 18.

# Requirements
- Python 3.10+
- SciPy

Install dependencies with:
```
pip install -r requirements.txt
```

# Usage
Run both entry points as modules from the repository root:

- `python -m src.example` runs a demo of the methods in `entry.py` and the file loading in `file_loader.py`
- `python -m src.main` launches the CLI to input user data, load file data, and analyze it. Only warnings are logged by default; pass `-v`/`--verbose` to also log every entry added or rejected (this prints your weight and calorie data). Pass `--data-file PATH` to choose where the log is saved (see [Your Data](#your-data))

# Your Data
The CLI keeps your log in a JSON file, by default `~/.calorie_tracker/log.json` in your home directory (never inside the repository). To use a different file, pass `--data-file PATH` or set the `CALORIE_TRACKER_DATA` environment variable; the flag wins over the variable. The path must end in `.json`.

- The log is loaded on startup (the CLI prints how many entries it loaded) and saved after every change: adding, importing, editing or deleting entries. Exiting with Ctrl-C or Ctrl-D loses nothing that was already saved.
- The file uses the same format as the JSON importer (`[{"date": "YYYY-MM-DD", "weight": 200.0, "calories": 2200}, ...]`), so you can copy it, back it up, or import it with "Load from file".
- Because it holds health data, the file is readable and writable only by you (permissions `600`; a new `~/.calorie_tracker` folder is `700`). Saves write a temporary file next to it and swap it in, so an interrupted save never leaves a half-written log.
- If the file can't be read back exactly (invalid JSON, a missing field, or entries that fail validation, e.g. after a hand edit), the CLI refuses to start and leaves the file untouched, rather than risk overwriting it. Fix or move the file, or point `--data-file` somewhere else.

# Running Tests
The project uses `pytest`. Install the development dependencies and run the suite from the repository root:
```
pip install -r requirements-dev.txt
pytest
```

# Why I'm Doing This Project
I wanted to combine my interest in fitness and nutrition with my growing skills in software engineering. Many commercial fitness apps are closed-source so users never see how calculations are made. 

This project also explicitly models how recommended calorie consumption changes in non-linear situations, such as the metabolic adjustments that occur during weight loss or weight gain phases.

# Goal
This project is my way to:
- Practice object-oriented programming and custom data structures  
- Apply scientific and mathematical concepts (calorie balance, optimization) in code  
- Build a practical tool that can help me and others understand nutrition data better
