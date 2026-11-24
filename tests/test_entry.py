from datetime import datetime

import logging
import math

import pytest

from src.entry import (
    ADAPT_KCAL_PER_LB,
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


# --- Duplicate dates ------------------------------------------------------

def test_duplicate_date_is_rejected():
    log = CaloriesLog()
    assert log.add_entry(DailyEntry(datetime(2025, 7, 1), 200, 2200)) is True
    assert log.add_entry(DailyEntry(datetime(2025, 7, 1), 199, 1800)) is False
    assert len(log) == 1
    assert log.first().calories == 2200  # original entry kept


def test_duplicate_date_with_different_time_is_rejected():
    log = CaloriesLog()
    assert log.add_entry(DailyEntry(datetime(2025, 7, 1, 8), 200, 2200)) is True
    assert log.add_entry(DailyEntry(datetime(2025, 7, 1, 20), 200.5, 2200)) is False


def test_duplicate_dates_no_longer_produce_negative_maintenance():
    log = make_log([(1, 200.0, 2000), (1, 201.0, 2000), (2, 200.0, 2000)])
    assert len(log) == 2
    assert MaintenanceCalculator(log).maintenance_calculator() == pytest.approx(2000)


# --- Maintenance math -----------------------------------------------------

def test_maintenance_exceeds_intake_when_weight_is_lost():
    # Ate 2000/day and lost weight => maintenance must be above intake.
    log = make_log([(1, 200.0, 2000), (11, 199.0, 2000)])
    maintenance = MaintenanceCalculator(log).maintenance_calculator()
    # Weigh-ins 10 days apart: -1 lb / 10 days = -0.1 lb/day => 2000 + 0.1*3500
    assert maintenance == pytest.approx(2350)
    assert maintenance > log.average_calories()


def test_maintenance_below_intake_when_weight_is_gained():
    log = make_log([(1, 200.0, 3000), (11, 202.0, 3000)])
    maintenance = MaintenanceCalculator(log).maintenance_calculator()
    # +2 lb over 10 days = +0.2 lb/day => 3000 - 0.2*3500
    assert maintenance == pytest.approx(2300)
    assert maintenance < log.average_calories()


def test_maintenance_uses_regression_slope_over_all_weigh_ins():
    # Steady 0.1 lb/day loss at 2000 kcal => true maintenance 2350.
    rows = [(day, 200.0 - 0.1 * (day - 1), 2000) for day in range(1, 11)]
    log = make_log(rows)
    assert log.weight_slope() == pytest.approx(-0.1)
    assert MaintenanceCalculator(log).maintenance_calculator() == pytest.approx(2350)


def test_single_noisy_weigh_in_does_not_dominate():
    # 21 days of steady 0.1 lb/day loss at 2000 kcal (true maintenance 2350),
    # but the final weigh-in carries +2.5 lb of water weight. A first/last
    # estimate would read this as a gain (maintenance ~1917, below intake).
    rows = [(day, 200.0 - 0.1 * (day - 1), 2000) for day in range(1, 22)]
    rows[-1] = (21, rows[-1][1] + 2.5, 2000)
    log = make_log(rows)
    assert log.weight_difference() < 0  # endpoints alone suggest gaining

    maintenance = MaintenanceCalculator(log).maintenance_calculator()
    assert maintenance > log.average_calories()  # still correctly reads as losing
    assert maintenance == pytest.approx(2350, abs=150)


def test_weight_slope_needs_two_distinct_dates():
    assert CaloriesLog().weight_slope() is None
    assert make_log([(1, 200, 2200)]).weight_slope() is None


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


@pytest.mark.parametrize("time_frame", [0, -1, -30])
def test_goal_planner_rejects_non_positive_time_frame(time_frame):
    with pytest.raises(ValueError):
        GoalPlanner(current_weight=200, target_weight=190, time_frame=time_frame, maintenance_calories=2500)


def test_optimized_loss_is_slightly_below_algebraic():
    planner = GoalPlanner(current_weight=200, target_weight=190, time_frame=100, maintenance_calories=2500)
    algebraic = planner.recommend_calories()  # 2150
    optimized = planner.recommend_calories_optimized()
    # Maintenance drops as weight is lost, so a slightly larger deficit is needed.
    assert optimized < algebraic
    assert algebraic - optimized < 150
    assert optimized == pytest.approx(2098, abs=5)


def test_optimized_gain_is_slightly_above_algebraic():
    planner = GoalPlanner(current_weight=200, target_weight=210, time_frame=100, maintenance_calories=2500)
    algebraic = planner.recommend_calories()  # 2850
    optimized = planner.recommend_calories_optimized()
    assert optimized > algebraic
    assert optimized - algebraic < 150
    assert optimized == pytest.approx(2902, abs=5)


def test_optimized_longer_loss_does_not_collapse_to_bound():
    # The old compounding model pinned this at the 800 kcal floor.
    planner = GoalPlanner(current_weight=200, target_weight=180, time_frame=180, maintenance_calories=2500)
    optimized = planner.recommend_calories_optimized()
    assert optimized == pytest.approx(2003, abs=5)
    assert planner.recommend_calories() - optimized < 150


def test_optimized_with_no_weight_change_returns_maintenance():
    planner = GoalPlanner(current_weight=200, target_weight=200, time_frame=30, maintenance_calories=2500)
    assert planner.recommend_calories_optimized() == pytest.approx(2500, abs=1)


def test_optimized_matches_closed_form_adaptation_model():
    # Continuous form of the model: lbs lost u(T) = D/k * (1 - exp(-k*T/3500))
    # for a daily deficit D, so D = u*k / (1 - exp(-k*T/3500)).
    k, T, u = ADAPT_KCAL_PER_LB, 120, 12
    expected = 2500 - u * k / (1 - math.exp(-k * T / 3500))
    planner = GoalPlanner(current_weight=200, target_weight=200 - u, time_frame=T, maintenance_calories=2500)
    assert planner.recommend_calories_optimized() == pytest.approx(expected, abs=10)


def test_optimized_warns_when_target_unreachable(caplog):
    planner = GoalPlanner(current_weight=200, target_weight=150, time_frame=10, maintenance_calories=2500)
    with caplog.at_level(logging.WARNING):
        value = planner.recommend_calories_optimized()
    assert value == pytest.approx(800, abs=1)
    assert "not reachable" in caplog.text


def test_optimized_does_not_warn_for_reachable_target(caplog):
    planner = GoalPlanner(current_weight=200, target_weight=190, time_frame=100, maintenance_calories=2500)
    with caplog.at_level(logging.WARNING):
        planner.recommend_calories_optimized()
    assert "not reachable" not in caplog.text


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


def test_weight_trend_reports_regression_rate():
    # 5 lb over 10 days (weigh-ins on day 1 and 11) is 0.50 lbs/day.
    losing = make_log([(1, 200.0, 2000), (11, 195.0, 2000)])
    assert TrendAnalyzer(losing).weight_trend() == "Losing weight: 0.50 lbs/day average"


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
