from datetime import datetime, timedelta

import pytest

from calorie_tracker.chart import BOTH_MARK, DEFAULT_WIDTH, RAW_MARK, TREND_MARK, render_weight_chart


def series(weights, start=datetime(2025, 7, 1), step_days=1):
    dates = [start + timedelta(days=i * step_days) for i in range(len(weights))]
    return dates, list(weights)


def assert_fits(chart, width=DEFAULT_WIDTH):
    assert all(len(line) <= width for line in chart.splitlines())


def plot_area(chart):
    # Drop the legend line and the x axis below the grid.
    return "\n".join(chart.splitlines()[1:-2])


def test_empty_series_gives_message():
    assert render_weight_chart([], [], []) == "No entries to chart."


def test_single_entry_renders_one_point():
    chart = render_weight_chart([datetime(2025, 7, 1)], [200.0], [200.0])
    assert_fits(chart)
    assert plot_area(chart).count(BOTH_MARK) == 1
    assert "2025-07-01" in chart


def test_flat_series_does_not_divide_by_zero():
    dates, weights = series([180.0] * 10)
    chart = render_weight_chart(dates, weights, weights)
    assert_fits(chart)
    assert plot_area(chart).count(BOTH_MARK) == 10


def test_raw_and_trend_marks_and_axis_labels():
    dates, raw = series([200, 198, 199, 196, 197, 195])
    trend = [200, 199.8, 199.7, 199.3, 199.1, 198.7]
    chart = render_weight_chart(dates, raw, trend)
    assert_fits(chart)
    lines = chart.splitlines()
    assert lines[0].startswith("Weight (lbs)")
    assert RAW_MARK in plot_area(chart) and TREND_MARK in plot_area(chart)
    assert lines[1].lstrip().startswith("200.0 |")
    assert lines[-1].strip().startswith("2025-07-01")
    assert lines[-1].endswith("2025-07-06")


def test_kg_axis():
    dates, raw = series([200, 196])
    chart = render_weight_chart(dates, raw, raw, unit="kg")
    assert chart.splitlines()[0].startswith("Weight (kg)")
    assert "90.7 |" in chart


def test_long_history_stays_within_width():
    # Three years of daily entries is far more points than columns.
    weights = [200 - (i % 30) * 0.1 - i * 0.01 for i in range(3 * 365)]
    dates, raw = series(weights)
    chart = render_weight_chart(dates, raw, raw)
    assert_fits(chart)
    assert len(chart.splitlines()) == 1 + 15 + 2


def test_irregular_gaps_and_narrow_width():
    dates = [datetime(2025, 1, 1), datetime(2025, 1, 2), datetime(2025, 3, 1), datetime(2025, 12, 31)]
    raw = [200, 199, 190, 180]
    chart = render_weight_chart(dates, raw, raw, width=10, height=2)
    # Too-small sizes are raised to a readable minimum instead of failing.
    assert_fits(chart, 40)
    assert len(chart.splitlines()) == 1 + 5 + 2


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        render_weight_chart([datetime(2025, 7, 1)], [200.0], [])
