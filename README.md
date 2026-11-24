# Calorie Tracker and Planner
A Python project that helps users estimate their maintenance calories(TDEE) based on tracked caloric intake and body weight over time instead of algebraic calculations based on weight and height.

The project supports importing data from `.csv` and `.json`, performs analysis with custom data structures, and even applies nonlinear optimization (sciPy minimize_scalar) to provide more realistic caloric recommendations when reverse engineering calories for a goal weight.

# Features
- Custom Data Structures with Object Oriented Programming:

  - LinkedList -> implementation for storing daily entries
  - DailyEntry, CaloriesLog, MaintenanceCalculator Classes

- Trend Analysis

  - Moving averages of weight or calories with TrendAnalyzer Class
  - Smoothed trend weight (an exponentially weighted moving average, Hacker's Diet style) and a terminal chart of scale weight vs. trend (see [Trend Chart](#trend-chart))

- Validation:

  - Ensures realistic entries (`EntryValidator`)
  - Rejects a second entry for a date that is already logged
  - Rejects weight changes of more than 5 lbs per day compared with the entries just before and after the new date (so back-filled days are checked too)
  - The CLI says why an entry was rejected (e.g. duplicate date, calories out of range), and how many rows of a file were skipped for each reason

- Caloric Recommendations:

  - Algebraic approach (linear math)
  - Optimized approach using scipy.optimize (nonlinear metabolic adaptation model)
  - Safety guardrails: recommendations stay between 1200 and 5000 kcal/day, and goals that need more than 2 lbs/week of loss (or intake outside that range) are flagged with the shortest safe time frame

- Pounds or Kilograms:
  - Enter and view weights in lbs or kg (see [Weight Units](#weight-units))

- File Import:
  - Import data from `.csv`, `.json`, and `.txt` files using `file_loader.py`
  - CSV and JSON files may give weights in kg (see [File Formats](#file-formats))

- Export:
  - Export your entries to `.csv` or `.json` from the CLI; the files import back with "Load from file"

- Saved Between Sessions:
  - The CLI saves your log after every change and loads it again on startup (see [Your Data](#your-data))
  - List, edit (re-validated against the other entries) and delete (with confirmation) entries by date

# How the Estimates Work
- **Maintenance calories** (`MaintenanceCalculator`): fits a least-squares line through every weigh-in (weight vs. day) to get the rate of weight change in lbs/day, then
  `maintenance = average calories - slope * 3500` (about 3500 kcal per lb of body weight). Using every weigh-in instead of only the first and last keeps a single noisy reading (e.g. water weight) from dominating. At least two different dates are needed. The weight trend in `TrendAnalyzer` uses the same slope.
- **Algebraic recommendation**: `maintenance + (target - current) * 3500 / days`, i.e. a constant deficit or surplus.
- **Optimized recommendation** (metabolic adaptation): simulates the plan day by day, with maintenance shifting by `ADAPT_KCAL_PER_LB` (10 kcal/day) for every lb lost or gained relative to the starting weight, and uses `scipy.optimize.minimize_scalar` to find the constant daily intake (1200 to 5000 kcal) that lands on the target weight. For losing weight it is slightly below the algebraic value, and for gaining slightly above. If the target can't be reached within those bounds (the best plan misses it by more than 0.1 lb), the bound is returned (and the goal is flagged by the safety guardrails below).
- **Trend weight** (`TrendAnalyzer.trend_weights`): an exponentially weighted moving average, as in John Walker's *The Hacker's Diet*. It starts at the first weigh-in, and each day moves `TREND_ALPHA` (0.1, i.e. 10%) of the way toward the scale reading: `trend = trend + 0.1 * (weight - trend)`. Day-to-day water-weight swings mostly cancel out, so the trend shows where your weight is really heading. Missed days count as days without a reading: after a gap of `n` days the trend moves `1 - 0.9**n` of the way, rather than a single 10% step.
- **Safety guardrails** (`GoalPlanner.safety_warnings`): both recommendations stay within `GoalPlanner.CALORIE_BOUNDS`, whose floor is `MIN_SAFE_CALORIES` (1200 kcal/day) and whose cap is `MAX_DAILY_CALORIES` (5000 kcal/day, also the most a logged entry may have). A goal is flagged when it needs more than `MAX_SAFE_LBS_PER_WEEK` (2 lbs/week) of loss or would need intake outside those bounds, and the warning includes the shortest time frame that avoids all of these limits (`GoalPlanner.min_safe_time_frame`). The CLI prints these warnings with every goal plan.

> **Disclaimer:** all numbers from this project are estimates only, not medical advice. Talk to a doctor or registered dietitian before making significant changes to your diet, especially if you are pregnant, have a medical condition, or are under 18.

# Requirements
- Python 3.10+
- SciPy (installed automatically)

Dependencies are declared in `pyproject.toml`. Install the package from the repository root, in a virtual environment if you like:
```
pip install -e .          # the app and its runtime dependencies
pip install -e ".[dev]"   # also pytest, ruff and mypy, for development
```
`pip install -r requirements.txt` and `pip install -r requirements-dev.txt` (run from the repository root) do the same two things.

# Usage
After installing:

- `calorie-tracker` (or `python -m calorie_tracker.main`) launches the CLI to input user data, load file data, and analyze it. Only warnings are logged by default; pass `-v`/`--verbose` to also log every entry added or rejected (this prints your weight and calorie data). Pass `--data-file PATH` to choose where the log is saved (see [Your Data](#your-data)), and `--units kg` or `--units lbs` to choose the weight unit for that session (see [Weight Units](#weight-units))
- `python -m calorie_tracker.example` runs a demo of the methods in `entry.py` and the file loading in `file_loader.py`

# Weight Units
Weights can be entered and shown in pounds (the default) or kilograms. Choose "Change weight unit" in the CLI menu; the choice is remembered for next time. `--units kg` (or `--units lbs`) uses that unit for one session without changing the remembered choice.

- Every weight prompt and display uses the chosen unit: adding and editing entries, the entry list, the summary, the goal planner (including its safety warnings), moving averages and the trend chart.
- Internally, and in the saved log, weights are always stored in pounds (converted with the exact factor 1 lb = 0.45359237 kg), so switching units never changes your data. The validation limits are defined in pounds too (50 to 600 lbs, at most 5 lbs per day), and rejection messages state them in pounds.

# File Formats
"Load from file" reads `.csv`, `.json` and `.txt` files with one entry per day:

- **CSV**: a header row with `date`, `weight` and `calories` columns (any order, any case), e.g. `2025-07-01,200,2200`.
- **JSON**: an array of objects with `date`, `weight` and `calories` fields, e.g. `[{"date": "2025-07-01", "weight": 200, "calories": 2200}]`.
- **TXT**: one `date, weight, calories` line per entry (commas or spaces); lines starting with `#` are ignored.

Dates are `YYYY-MM-DD`. Weights are in lbs unless the file says otherwise (CSV and JSON only):

- an optional `unit` (or `weight_unit`) column or field per entry, `lbs` or `kg` (also `lb`, `pounds`, `kgs`, `kilograms`), e.g. `date,weight,calories,unit` / `2025-07-01,90.5,2200,kg`. If an entry has both, they must agree.
- or a `weight_kg` column or field in place of `weight`, e.g. `date,weight_kg,calories`

An entry may not have both `weight` and `weight_kg`. Weights that don't say their unit (a plain `weight` with a blank or missing `unit`, and every `.txt` weight) are read as lbs. When the CLI is set to kg and a file has such weights, it asks whether they are in lbs or kg before adding them (Enter means lbs).

# Exporting
"Export entries" writes every entry to a `.csv` or `.json` file at a path you enter. Weights are written in your chosen unit, with a `unit` column, so the file imports back the same with "Load from file" whatever unit is chosen at the time (kg values are rounded to 6 decimal places, well under a gram). If the file already exists you are asked before it is replaced, and the CLI won't export over its own data or settings file. Like the data file, exports are readable only by you (permissions `600`).

# Trend Chart
"Analyze trends" then "Weight trend chart" draws your scale readings (`o`) and the smoothed trend weight (`*`, `@` where they overlap) against time, within 80 columns:

```
Weight (lbs): o scale  * trend  @ both
200.0 |@***
      |    *****
      |         *****
      |              ****
      |                  *****
      |    o                  ******
      |                             ******
198.4 |                                   *******
      |       o                                  ******
      |           o                                    *******
      |               o                                       **********
      |                  o   o   o  o   o                               ******
      |
      |                                     o   o  o   o
196.8 |                                                    o  o   o   o  o   o
      +-----------------------------------------------------------------------
       2025-07-01                                                   2025-07-20
```

The trend lags the scale on purpose: a single high or low reading only moves it by a tenth of the difference.

# Your Data
The CLI keeps your log in a JSON file, by default `~/.calorie_tracker/log.json` in your home directory (never inside the repository). To use a different file, pass `--data-file PATH` or set the `CALORIE_TRACKER_DATA` environment variable; the flag wins over the variable. The path must end in `.json`.

- The log is loaded on startup (the CLI prints how many entries it loaded) and saved after every change: adding, importing, editing or deleting entries. Exiting with Ctrl-C or Ctrl-D loses nothing that was already saved.
- The file uses the same format as the JSON importer (`[{"date": "YYYY-MM-DD", "weight": 200.0, "calories": 2200}, ...]`, weights in lbs), so you can copy it, back it up, or import it with "Load from file".
- Your weight unit choice is kept in a small settings file next to it, named after the data file (`log.json` -> `log.settings.json`), so the log itself stays a plain list of entries. If the settings file is missing or can't be read, the CLI uses lbs.
- Because it holds health data, the file is readable and writable only by you (permissions `600`; a new `~/.calorie_tracker` folder is `700`). Saves write a temporary file next to it and swap it in, so an interrupted save never leaves a half-written log.
- If the data file is a symlink (e.g. into a synced folder), saves update the file it points to and keep the link.
- An empty file is treated as an empty log. If the file can't be read back exactly (it or its folder isn't readable, invalid JSON, a missing field, or entries that fail validation, e.g. after a hand edit), the CLI refuses to start and leaves the file untouched, rather than risk overwriting it. Fix or move the file, or point `--data-file` somewhere else.
- If a save fails (e.g. the folder is read-only), the CLI warns you and keeps going; on exit it tries once more and warns if your changes still couldn't be saved.

# Development
Install the development dependencies, then run the tests, linter, formatter check and type checker from the repository root:
```
pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy
```
Their settings live in `pyproject.toml`. `ruff format .` reformats the code, and `ruff check --fix .` fixes the lint findings it can. The same checks run in GitHub Actions (`.github/workflows/ci.yml`) on every push and pull request, on Python 3.10 to 3.13.

# Why I'm Doing This Project
I wanted to combine my interest in fitness and nutrition with my growing skills in software engineering. Many commercial fitness apps are closed-source so users never see how calculations are made. 

This project also explicitly models how recommended calorie consumption changes in non-linear situations, such as the metabolic adjustments that occur during weight loss or weight gain phases.

# Goal
This project is my way to:
- Practice object-oriented programming and custom data structures  
- Apply scientific and mathematical concepts (calorie balance, optimization) in code  
- Build a practical tool that can help me and others understand nutrition data better
