"""Plain-text chart of scale weight vs. smoothed trend weight, for the terminal."""

from datetime import datetime

from .units import LBS, from_lbs, normalize_unit

RAW_MARK = "o"
TREND_MARK = "*"
BOTH_MARK = "@"

DEFAULT_WIDTH = 78
DEFAULT_HEIGHT = 15
MIN_WIDTH = 40
MIN_HEIGHT = 5


def _day(value):
    return value.date() if isinstance(value, datetime) else value


def render_weight_chart(
    dates, raw, trend, unit: str = LBS, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT
) -> str:
    """Chart of the scale readings (o) and trend weight (*, joined into a line)
    against time, at most `width` columns wide. `raw` and `trend` are in lbs and
    are shown in `unit`; `dates` are datetimes or dates in ascending order."""
    if not (len(dates) == len(raw) == len(trend)):
        raise ValueError("dates, raw and trend must have the same length")
    if not dates:
        return "No entries to chart."
    unit = normalize_unit(unit)
    width = max(width, MIN_WIDTH)
    height = max(height, MIN_HEIGHT)

    raw = [from_lbs(value, unit) for value in raw]
    trend = [from_lbs(value, unit) for value in trend]
    low, high = min(raw + trend), max(raw + trend)
    if high - low < 1:
        # A flat (or single-point) series would divide by zero; give it some room.
        middle = (high + low) / 2
        low, high = middle - 0.5, middle + 0.5

    def row_of(value):
        return round((high - value) / (high - low) * (height - 1))

    def value_at(row):
        return high - row * (high - low) / (height - 1)

    labelled = {0: f"{high:.1f}", height // 2: f"{value_at(height // 2):.1f}", height - 1: f"{low:.1f}"}
    label_width = max(len(label) for label in labelled.values())
    plot_width = width - label_width - 2  # room for " |"

    days = [_day(date) for date in dates]
    span = (days[-1] - days[0]).days

    def column_of(day):
        return 0 if span == 0 else round((day - days[0]).days / span * (plot_width - 1))

    grid = [[" "] * plot_width for _ in range(height)]
    columns = [column_of(day) for day in days]

    # Trend: a line through every point, filling the columns in between.
    for index, (column, value) in enumerate(zip(columns, trend, strict=True)):
        if index == 0:
            grid[row_of(value)][column] = TREND_MARK
            continue
        start, previous = columns[index - 1], trend[index - 1]
        for c in range(start, column + 1):
            fraction = 1 if column == start else (c - start) / (column - start)
            grid[row_of(previous + (value - previous) * fraction)][c] = TREND_MARK

    for column, value in zip(columns, raw, strict=True):
        cell = grid[row_of(value)]
        cell[column] = BOTH_MARK if cell[column] in (TREND_MARK, BOTH_MARK) else RAW_MARK

    lines = [f"Weight ({unit}): {RAW_MARK} scale  {TREND_MARK} trend  {BOTH_MARK} both"]
    for row, cells in enumerate(grid):
        label = labelled.get(row, "")
        lines.append(f"{label:>{label_width}} |{''.join(cells)}".rstrip())
    lines.append(f"{'':>{label_width}} +{'-' * plot_width}")

    first, last = days[0].isoformat(), days[-1].isoformat()
    axis = first
    if span and plot_width >= len(first) + len(last) + 1:
        axis = first + last.rjust(plot_width - len(first))
    lines.append(f"{'':>{label_width}}  {axis}")
    return "\n".join(lines)
