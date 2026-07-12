from datetime import datetime

import pytest

from src.entry import (
    CaloriesLog,
    DailyEntry,
    EntryValidator,
    GoalPlanner,
    MaintenanceCalculator,
    TrendAnalyzer,
)


def make_log(rows):
    """rows: list of (day, weight, calories) in July 2025."""
    log = CaloriesLog()
    for day, weight, calories in rows:
        log.add_entry(DailyEntry(datetime(2025, 7, day), weight, calories))
    return log


# --- Ordering invariant ---------------------------------------------------

def test_entries_are_sorted_regardless_of_insertion_order():
    log = make_log([(4, 197.9, 2100), (1, 200, 2200), (3, 198.2, 2150), (2, 198.8, 2200)])
    days = [e.date.day for e in log.get_entries_list()]
    assert days == [1, 2, 3, 4]


def test_days_tracked_and_weight_difference_use_chronological_ends():
    # Inserted out of order; head must be earliest, tail latest.
    log = make_log([(10, 198.0, 2000), (1, 200.0, 2000)])
    assert log.days_tracked() == 10  # (10 - 1) + 1
    assert log.weight_difference() == pytest.approx(2.0)  # 200 - 198 (start - end)


# --- Empty / single-entry handling ---------------------------------------

def test_empty_log_returns_none_not_zero():
    log = CaloriesLog()
    assert log.average_calories() is None
    assert log.weight_difference() is None
    assert MaintenanceCalculator(log).maintenance_calculator() is None


def test_single_entry_has_no_maintenance_estimate():
    log = make_log([(1, 200, 2200)])
    assert log.weight_difference() is None
    assert MaintenanceCalculator(log).maintenance_calculator() is None


# --- Maintenance math -----------------------------------------------------

def test_maintenance_exceeds_intake_when_weight_is_lost():
    # Ate 2000/day and lost weight => maintenance must be above intake.
    log = make_log([(1, 200.0, 2000), (11, 199.0, 2000)])
    maintenance = MaintenanceCalculator(log).maintenance_calculator()
    # avg=2000, weight_diff=1 lb, days=11 => 2000 + (1*3500/11)
    assert maintenance == pytest.approx(2000 + 3500 / 11)
    assert maintenance > log.average_calories()


def test_maintenance_below_intake_when_weight_is_gained():
    log = make_log([(1, 200.0, 3000), (11, 202.0, 3000)])
    maintenance = MaintenanceCalculator(log).maintenance_calculator()
    assert maintenance < log.average_calories()


# --- Goal planner ---------------------------------------------------------

def test_recommend_calories_direction():
    lose = GoalPlanner(current_weight=200, target_weight=190, time_frame=100, maintenance_calories=2500)
    gain = GoalPlanner(current_weight=200, target_weight=210, time_frame=100, maintenance_calories=2500)
    assert lose.recommend_calories() < 2500  # deficit to lose
    assert gain.recommend_calories() > 2500  # surplus to gain
    # -10 lb over 100 days => -350 kcal/day
    assert lose.recommend_calories() == pytest.approx(2500 + (-10 * 3500 / 100))


def test_recommend_calories_optimized_stays_within_bounds():
    planner = GoalPlanner(current_weight=200, target_weight=195, time_frame=60, maintenance_calories=2500)
    value = planner.recommend_calories_optimized()
    assert 800 <= value <= 5000


# --- Trend analysis -------------------------------------------------------

def test_moving_average_windows():
    log = make_log([(1, 200, 2000), (2, 200, 2100), (3, 200, 2200), (4, 200, 2300)])
    assert TrendAnalyzer(log).moving_average(2, "calories") == [2050, 2150, 2250]


def test_moving_average_returns_empty_when_window_too_large():
    log = make_log([(1, 200, 2000), (2, 200, 2100)])
    assert TrendAnalyzer(log).moving_average(5, "calories") == []


def test_moving_average_rejects_unknown_field():
    log = make_log([(1, 200, 2000), (2, 200, 2100)])
    with pytest.raises(ValueError):
        TrendAnalyzer(log).moving_average(2, "steps")


def test_weight_trend_classification():
    losing = make_log([(1, 200.0, 2000), (11, 195.0, 2000)])
    gaining = make_log([(1, 195.0, 2000), (11, 200.0, 2000)])
    stable = make_log([(1, 200.0, 2000), (11, 200.1, 2000)])
    assert TrendAnalyzer(losing).weight_trend().startswith("Losing")
    assert TrendAnalyzer(gaining).weight_trend().startswith("Gaining")
    assert TrendAnalyzer(stable).weight_trend().startswith("Stable")


def test_weight_trend_insufficient_data():
    assert TrendAnalyzer(CaloriesLog()).weight_trend() == "Insufficient data"


# --- Validation -----------------------------------------------------------

def test_validator_accepts_reasonable_entry():
    assert EntryValidator.is_valid(DailyEntry(datetime(2025, 7, 1), 200, 2200)) is True


@pytest.mark.parametrize("weight,calories", [
    (200, 100),    # calories too low
    (200, 9000),   # calories too high
    (30, 2200),    # weight too low
    (900, 2200),   # weight too high
])
def test_validator_rejects_out_of_range(weight, calories):
    assert EntryValidator.is_valid(DailyEntry(datetime(2025, 7, 1), weight, calories)) is False


def test_validator_rejects_large_one_day_swing():
    log = CaloriesLog()
    assert log.add_entry(DailyEntry(datetime(2025, 7, 1), 200, 2200)) is True
    # 6 lb change in a single day is implausible and must be rejected.
    assert log.add_entry(DailyEntry(datetime(2025, 7, 2), 206, 2200)) is False
    assert len(log) == 1
