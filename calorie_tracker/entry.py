from __future__ import annotations

import logging
import math
import numbers
import statistics
from collections.abc import Iterable, Iterator
from datetime import date as Date
from datetime import datetime

from scipy.optimize import minimize_scalar

from .units import KG, LBS, from_lbs, normalize_unit

# Logging is configured by the entry points (main.py, example.py), not here.
# Messages that include entry data (weight, calories) are DEBUG only.
logger = logging.getLogger(__name__)

# Energy content of one pound of body weight (standard approximation).
KCAL_PER_LB = 3500

# Metabolic adaptation used by GoalPlanner.recommend_calories_optimized:
# maintenance shifts by this many kcal/day per lb of weight lost (or gained)
# relative to the starting weight.
ADAPT_KCAL_PER_LB = 10

# Largest plausible change in body weight per day between two weigh-ins; a
# bigger swing is almost certainly a typo or a unit mix-up.
MAX_LBS_PER_DAY = 5

# Plausible daily intake for a logged entry; EntryValidator rejects anything
# outside it. MAX_DAILY_CALORIES also caps GoalPlanner's recommendations.
MIN_LOGGED_CALORIES = 800
MAX_DAILY_CALORIES = 5000

# Plausible body weight (lbs) for a logged entry.
MIN_WEIGHT_LBS = 50
MAX_WEIGHT_LBS = 600

# Health guardrails for goal planning (common general guidelines, not medical
# advice): recommendations never go below MIN_SAFE_CALORIES, and a plan that
# loses more than MAX_SAFE_LBS_PER_WEEK is flagged by GoalPlanner.safety_warnings.
MIN_SAFE_CALORIES = 1200
MAX_SAFE_LBS_PER_WEEK = 2

DAYS_PER_WEEK = 7

# Smoothing factor for TrendAnalyzer.trend_weights: each day the trend moves this
# fraction of the way toward the scale reading (the Hacker's Diet uses 0.1).
TREND_ALPHA = 0.1

# TrendAnalyzer.weight_trend calls a slope smaller than this (lbs/day) stable.
STABLE_LBS_PER_DAY = 0.05

# How far (lbs) the optimized plan may miss the target before it is reported
# as unreachable within GoalPlanner.CALORIE_BOUNDS.
UNREACHABLE_TOLERANCE_LBS = 0.1

# How many days past its first estimate GoalPlanner.min_safe_time_frame tries
# before deciding that no time frame satisfies every bound.
MAX_EXTRA_SAFE_DAYS = 10


def _is_number(value: object, kind: type) -> bool:
    # bool is a subclass of int, but True/False is never a real measurement.
    # Taking `object` keeps type checkers from treating the check as always true.
    return isinstance(value, kind) and not isinstance(value, bool)


class DailyEntry:
    def __init__(self, date: datetime, weight: float, calories: int):
        if not isinstance(date, datetime):
            raise TypeError("Date must be a datetime object")
        if not _is_number(weight, numbers.Real):
            raise TypeError(f"Weight must be a number, got {weight!r}")
        if not _is_number(calories, numbers.Integral):
            raise TypeError(f"Calories must be a whole number, got {calories!r}")
        self._date = date
        self._weight = weight
        self._calories = calories

    # introduce property decorators for getter method
    @property
    def date(self) -> datetime:
        return self._date

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def calories(self) -> int:
        return self._calories

    def __str__(self) -> str:
        return f"DailyEntry({self._date.strftime('%Y-%m-%d')}, {self._weight}lbs, {self._calories}cals)"


class Node:
    def __init__(self, data: DailyEntry):
        self._data = data
        self._next: Node | None = None


class LinkedList:
    def __init__(self):
        self._head: Node | None = None
        self._tail: Node | None = None
        self._length = 0

    def append(self, data: DailyEntry):
        new_node = Node(data)
        # If the list is empty, set the new node as both head and tail
        if self._head is None or self._tail is None:
            self._head = new_node
            self._tail = new_node

        else:
            self._tail._next = new_node  # Link the new node to the end of the list
            self._tail = new_node  # Update the tail to the new node
        self._length += 1

    def insert_sorted(self, data: DailyEntry):
        # Insert keeping the list sorted ascending by date, so the head is always
        # the earliest entry and the tail the latest, regardless of insertion order.
        # Entries with an equal date preserve their insertion order (stable).
        new_node = Node(data)
        if self._head is None or self._tail is None:
            self._head = new_node
            self._tail = new_node
        elif data.date < self._head._data.date:
            new_node._next = self._head
            self._head = new_node
        elif data.date >= self._tail._data.date:
            self._tail._next = new_node
            self._tail = new_node
        else:
            current = self._head
            while current._next is not None and current._next._data.date <= data.date:
                current = current._next
            new_node._next = current._next
            current._next = new_node
        self._length += 1

    def remove(self, data: DailyEntry) -> bool:
        # Unlink the node holding this exact object (compared by identity, not
        # value); returns False when it isn't in the list.
        previous = None
        current = self._head
        while current and current._data is not data:
            previous = current
            current = current._next
        if current is None:
            return False
        if previous is None:
            self._head = current._next
        else:
            previous._next = current._next
        if current is self._tail:
            self._tail = previous
        self._length -= 1
        return True

    def __iter__(self) -> Iterator[DailyEntry]:
        current = self._head
        while current:
            yield current._data
            current = current._next

    def __len__(self) -> int:
        return self._length

    @property
    def first(self) -> DailyEntry | None:
        return self._head._data if self._head else None

    @property
    def last(self) -> DailyEntry | None:
        return self._tail._data if self._tail else None


class CaloriesLog:
    def __init__(self):
        self._entries = LinkedList()
        self._dates = set()  # calendar days already logged, for duplicate detection

    def rejection_reason(self, entry: DailyEntry) -> str | None:
        """Short reason why add_entry would reject this entry, or None if it would be added.
        The reason never includes the entry's weight or calories."""
        # One entry per calendar day; a second one would skew every estimate.
        if entry.date.date() in self._dates:
            return "an entry for that date already exists"
        return EntryValidator.rejection_reason(entry, self._entries)

    def add_entry(self, entry: DailyEntry) -> bool:
        reason = self.rejection_reason(entry)
        if reason is not None:
            logger.debug("Rejected entry (%s): %s", reason, entry)
            return False
        self._entries.insert_sorted(entry)
        self._dates.add(entry.date.date())
        logger.debug("Added entry: %s", entry)
        return True

    @staticmethod
    def _day(date: Date) -> Date:
        # Accept a datetime or a plain date; entries are keyed by calendar day.
        return date.date() if isinstance(date, datetime) else date

    def get_entry(self, date: Date) -> DailyEntry | None:
        """The entry logged for this calendar day, or None."""
        day = self._day(date)
        if day not in self._dates:
            return None
        return next(entry for entry in self._entries if entry.date.date() == day)

    def remove_entry(self, date: Date) -> DailyEntry | None:
        """Remove the entry for this calendar day; return it, or None if there was none."""
        entry = self.get_entry(date)
        if entry is None:
            return None
        self._entries.remove(entry)
        self._dates.discard(entry.date.date())
        logger.debug("Removed entry: %s", entry)
        return entry

    def update_rejection_reason(self, date: Date, weight: float, calories: int) -> str | None:
        """Short reason why update_entry would reject these values, or None if it would apply them."""
        existing = self.get_entry(date)
        if existing is None:
            return "no entry for that date"
        replacement = DailyEntry(existing.date, weight, calories)
        # Validate against every other entry, as if the old one were already gone.
        others = [entry for entry in self._entries if entry is not existing]
        return EntryValidator.rejection_reason(replacement, others)

    def update_entry(self, date: Date, weight: float, calories: int) -> bool:
        """Replace the weight and calories logged for this calendar day after
        re-validating them. Returns False, leaving the log unchanged, when there
        is no entry for that day or the new values are rejected."""
        reason = self.update_rejection_reason(date, weight, calories)
        if reason is not None:
            logger.debug("Rejected update for %s (%s)", self._day(date), reason)
            return False
        existing = self.get_entry(date)
        assert existing is not None  # update_rejection_reason checked it exists
        replacement = DailyEntry(existing.date, weight, calories)
        # Same date, so remove + insert_sorted puts it back in the same position.
        self._entries.remove(existing)
        self._entries.insert_sorted(replacement)
        logger.debug("Updated entry: %s -> %s", existing, replacement)
        return True

    # Calculate average calories using all entries (None when there is no data)
    def average_calories(self) -> float | None:
        if len(self._entries) == 0:
            return None
        return sum(entry.calories for entry in self._entries) / len(self._entries)

    # Calculate weight difference (start - end); None when there are fewer than 2 entries
    def weight_difference(self) -> float | None:
        first, last = self._entries.first, self._entries.last
        if len(self._entries) < 2 or first is None or last is None:  # need a head and tail
            return None
        return first.weight - last.weight  # start weight - end weight

    # Calculate days tracked
    def days_tracked(self) -> int:
        first, last = self._entries.first, self._entries.last
        if len(self._entries) < 2 or first is None or last is None:  # need a head and tail
            return len(self._entries)
        return (last.date - first.date).days + 1

    # Least-squares slope of weight vs. day offset, in lbs/day (positive = gaining).
    # Uses every weigh-in, so one noisy reading can't dominate the estimate.
    # None when there are fewer than 2 distinct dates.
    def weight_slope(self) -> float | None:
        first = self._entries.first
        if len(self._entries) < 2 or first is None:
            return None
        start = first.date.date()
        days = [(entry.date.date() - start).days for entry in self._entries]
        if len(set(days)) < 2:
            return None
        weights = [entry.weight for entry in self._entries]
        return statistics.linear_regression(days, weights).slope

    # First (earliest) and last (latest) entries, or None when the log is empty
    @property
    def first(self) -> DailyEntry | None:
        return self._entries.first

    @property
    def last(self) -> DailyEntry | None:
        return self._entries.last

    def __len__(self) -> int:
        return len(self._entries)

    # Allow iteration over the log
    def __iter__(self) -> Iterator[DailyEntry]:
        yield from self._entries

    # Get List of all entries
    def get_entries_list(self) -> list[DailyEntry]:
        return list(self._entries)


class MaintenanceCalculator:
    def __init__(self, calories_log: CaloriesLog):
        self._log = calories_log

    def estimate(self) -> float | None:
        """Estimated maintenance calories per day, or None with fewer than two distinct dates."""
        avg_cals = self._log.average_calories()
        slope = self._log.weight_slope()

        # Need at least two distinct dates to estimate maintenance.
        if avg_cals is None or slope is None:
            return None

        # Gaining (slope > 0) means intake was above maintenance, and vice versa.
        return avg_cals - slope * KCAL_PER_LB


class TrendAnalyzer:
    def __init__(self, log: CaloriesLog):
        self._log = log

    def moving_average(self, window_size: int, field: str = "calories") -> list[float]:
        if field not in ("calories", "weight"):
            raise ValueError("Field must be 'calories' or 'weight'")

        values: list[float]
        if field == "calories":
            values = [entry.calories for entry in self._log]
        else:
            values = [entry.weight for entry in self._log]

        if len(values) < window_size or window_size <= 0:  # Check if the window size is valid
            return []

        moving_averages = []

        for i in range(len(values) - window_size + 1):  # Iterate through the list
            window = values[i : i + window_size]  # Get the current window
            average = sum(window) / window_size
            moving_averages.append(average)

        return moving_averages

    def trend_weights(self, alpha: float = TREND_ALPHA) -> list[float]:
        """Smoothed trend weight (lbs) for each entry, oldest first: an exponentially
        weighted moving average that starts at the first weigh-in and moves `alpha`
        of the way toward each new reading per day. Missed days count as days
        without a reading, so after a gap of n days the trend moves
        1 - (1 - alpha)**n of the way instead of jumping a full alpha step per entry.
        Empty when the log is empty."""
        if not _is_number(alpha, numbers.Real) or not 0 < alpha <= 1:
            raise ValueError(f"alpha must be a number in (0, 1], got {alpha!r}")
        trend = []
        previous = None
        for entry in self._log:
            if previous is None:
                value = entry.weight
            else:
                gap = max((entry.date.date() - previous.date.date()).days, 1)
                step = 1 - (1 - alpha) ** gap
                value = trend[-1] + step * (entry.weight - trend[-1])
            trend.append(value)
            previous = entry
        return trend

    def weight_trend(self, unit: str = LBS) -> str:
        rate = self._log.weight_slope()  # lbs/day; positive means gaining
        if rate is None:
            return "Insufficient data"
        days = self._log.days_tracked()
        unit = normalize_unit(unit)
        shown = abs(from_lbs(rate, unit))

        # The threshold is in lbs/day, like the slope; only the display is converted.
        if abs(rate) < STABLE_LBS_PER_DAY:
            return f"Stable weight (~{shown:.2f} {unit}/day over {days} days)"
        elif rate < 0:
            return f"Losing weight: {shown:.2f} {unit}/day average"
        else:
            return f"Gaining weight: {shown:.2f} {unit}/day average"


class EntryValidator:
    CALORIE_RANGE = (MIN_LOGGED_CALORIES, MAX_DAILY_CALORIES)
    WEIGHT_RANGE = (MIN_WEIGHT_LBS, MAX_WEIGHT_LBS)

    # Weight checks allow this much slack (about 5 mg) so a weight that sits
    # exactly on a limit still passes after a kg round trip, e.g. an export in
    # kg read back, which can move it by a few millionths of a pound.
    _WEIGHT_TOLERANCE_LBS = 1e-5

    @staticmethod
    def is_valid(entry: DailyEntry, existing_entries: Iterable[DailyEntry] | None = None) -> bool:
        return EntryValidator.rejection_reason(entry, existing_entries) is None

    @staticmethod
    def rejection_reason(entry: DailyEntry, existing_entries: Iterable[DailyEntry] | None = None) -> str | None:
        """Short reason why the entry fails validation, or None when it is valid."""
        low, high = EntryValidator.CALORIE_RANGE
        if not (low <= entry.calories <= high):
            return f"calories out of range ({low}-{high})"

        low, high = EntryValidator.WEIGHT_RANGE
        tolerance = EntryValidator._WEIGHT_TOLERANCE_LBS
        if not (low - tolerance <= entry.weight <= high + tolerance):
            return f"weight out of range ({low}-{high} lbs)"

        if not isinstance(entry.date, datetime):
            return "date is not a datetime"

        # Compare against the chronological neighbours rather than only the latest
        # entry, so back-filled days are checked too. The allowed change scales
        # with the number of days between the two weigh-ins.
        day = entry.date.date()
        before = after = None
        for existing in existing_entries or ():
            if existing.date.date() <= day:
                before = existing
            else:
                after = existing
                break

        for neighbour in (before, after):
            if neighbour is None:
                continue
            day_gap = max(abs((day - neighbour.date.date()).days), 1)
            if abs(entry.weight - neighbour.weight) > MAX_LBS_PER_DAY * day_gap + tolerance:
                return f"weight change too large compared with a nearby entry (more than {MAX_LBS_PER_DAY} lbs per day)"

        return None


class GoalPlanner:
    # Daily intake range for recommendations; the floor is the safety minimum.
    CALORIE_BOUNDS = (MIN_SAFE_CALORIES, MAX_DAILY_CALORIES)

    # Safety margin added to every comparison below so tiny floating-point
    # errors can't flip a plan that sits exactly on a limit.
    _EPS_LBS = 1e-9
    _EPS_KCAL = 1e-6

    def __init__(self, current_weight: float, target_weight: float, time_frame: int, maintenance_calories: float):
        # bool is an int subclass but never a meaningful number of days
        if isinstance(time_frame, bool) or not isinstance(time_frame, int):
            raise TypeError(f"Time frame must be a whole number of days, got {time_frame!r}")
        if time_frame <= 0:
            raise ValueError(f"Time frame must be a positive number of days, got {time_frame}")
        for name, value in (
            ("Current weight", current_weight),
            ("Target weight", target_weight),
            ("Maintenance calories", maintenance_calories),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number, got {value!r}")
        self._current_weight = current_weight
        self._target_weight = target_weight
        self._time_frame = time_frame
        self._maintenance = maintenance_calories

    @property
    def current_weight(self) -> float:
        return self._current_weight

    @property
    def target_weight(self) -> float:
        return self._target_weight

    @property
    def time_frame(self) -> int:
        return self._time_frame

    @property
    def maintenance_calories(self) -> float:
        return self._maintenance

    def recommend_calories(self) -> float:
        # Constant deficit or surplus, kept within CALORIE_BOUNDS (never below the safe minimum).
        low, high = self.CALORIE_BOUNDS
        return min(max(self._required_intake(self._time_frame, adaptive=False), low), high)

    def _required_intake(self, days: int, adaptive: bool) -> float:
        # Constant daily intake that reaches the target in `days`, ignoring any bounds.
        weight_diff = self._target_weight - self._current_weight
        if not adaptive or ADAPT_KCAL_PER_LB == 0:
            return self._maintenance + weight_diff * KCAL_PER_LB / days
        # Closed form of the day-by-day model in recommend_calories_optimized:
        # eating c kcal/day changes weight by (c - maintenance) / k * (1 - r**t)
        # after t days, with k = ADAPT_KCAL_PER_LB and r = 1 - k / KCAL_PER_LB.
        r = 1 - ADAPT_KCAL_PER_LB / KCAL_PER_LB
        return self._maintenance + weight_diff * ADAPT_KCAL_PER_LB / (1 - r**days)

    def _is_too_fast(self, days: int) -> bool:
        loss_per_week = (self._current_weight - self._target_weight) / days * DAYS_PER_WEEK
        return loss_per_week > MAX_SAFE_LBS_PER_WEEK + self._EPS_LBS

    def _needed_range(self, days: int) -> tuple[float, float]:
        # Intake needed by the algebraic and adaptive models, lowest first.
        a = self._required_intake(days, adaptive=False)
        b = self._required_intake(days, adaptive=True)
        return min(a, b), max(a, b)

    def _is_below_floor(self, days: int) -> bool:
        # Either model needing less than the floor means the capped plan falls short.
        return self._needed_range(days)[0] < self.CALORIE_BOUNDS[0] - self._EPS_KCAL

    def _is_above_cap(self, days: int) -> bool:
        # Either model needing more than the upper bound means the plan falls short.
        return self._needed_range(days)[1] > self.CALORIE_BOUNDS[1] + self._EPS_KCAL

    def _is_unsafe(self, days: int) -> bool:
        return self._is_too_fast(days) or self._is_below_floor(days) or self._is_above_cap(days)

    def min_safe_time_frame(self) -> int | None:
        """Fewest days in which the target can be reached without losing more than
        MAX_SAFE_LBS_PER_WEEK or eating outside CALORIE_BOUNDS, or None when no
        time frame can (maintenance is too close to, or outside, the bounds)."""
        low, high = self.CALORIE_BOUNDS
        change = abs(self._target_weight - self._current_weight)
        losing = self._target_weight < self._current_weight
        if change == 0:
            return None if self._is_unsafe(1) else 1

        # Largest daily deficit (losing) or surplus (gaining) the bounds allow.
        spare = self._maintenance - low if losing else high - self._maintenance
        k = ADAPT_KCAL_PER_LB
        if spare <= 0 or change * k >= spare:
            return None
        if k == 0:
            bound_days = change * KCAL_PER_LB / spare
        else:
            # Solve _required_intake(days, adaptive=True) == the bound for days;
            # the algebraic model always needs fewer days than this.
            bound_days = math.log(1 - change * k / spare) / math.log(1 - k / KCAL_PER_LB)
        rate_days = change * DAYS_PER_WEEK / MAX_SAFE_LBS_PER_WEEK if losing else 0

        # Round up, then step past any floating-point error so the answer agrees
        # exactly with the checks used by safety_warnings. If a few extra days
        # don't help, the other bound is in the way and no time frame works.
        days = max(1, math.ceil(max(bound_days, rate_days)))
        while days > 1 and not self._is_unsafe(days - 1):
            days -= 1
        for _ in range(MAX_EXTRA_SAFE_DAYS):
            if not self._is_unsafe(days):
                return days
            days += 1
        return None

    def safety_warnings(self, unit: str = LBS) -> list[str]:
        """Human-readable warnings for an unsafe goal; empty when the plan is fine.
        Weights are shown in `unit`; the limits themselves are always checked in lbs."""
        warnings = []
        low, high = self.CALORIE_BOUNDS
        days = self._time_frame
        loss = self._current_weight - self._target_weight
        unit = normalize_unit(unit)
        shown_loss = from_lbs(loss, unit)
        shown_target = round(from_lbs(self._target_weight, unit), 2)
        shown_limit = round(from_lbs(MAX_SAFE_LBS_PER_WEEK, unit), 2)
        # The kg limit is 0.91 kg/week, so one decimal could print a rate of 0.9 as too fast.
        places = 2 if unit == KG else 1

        if self._is_too_fast(days):
            warnings.append(
                f"Losing {shown_loss:.1f} {unit} in {days} days is about "
                f"{shown_loss / days * DAYS_PER_WEEK:.{places}f} {unit}/week, "
                f"faster than the {shown_limit:g} {unit}/week generally considered safe."
            )
        if self._is_below_floor(days):
            warnings.append(
                f"Reaching {shown_target:g} {unit} in {days} days would require eating below "
                f"{low} kcal/day. Recommendations never go below {low} "
                f"kcal/day, so the target will not be reached in that time."
            )
        if self._is_above_cap(days):
            warnings.append(
                f"Reaching {shown_target:g} {unit} in {days} days would require eating more than "
                f"{high} kcal/day. Recommendations never go above {high} "
                f"kcal/day, so the target will not be reached in that time."
            )

        if warnings:
            safe_days = self.min_safe_time_frame()
            if safe_days is None:
                warnings.append(
                    f"With an estimated maintenance of {self._maintenance:.0f} kcal/day, this target "
                    f"can't be reached while eating between {low} and {high} kcal/day. "
                    f"Consider a more modest target, or check that your log is complete."
                )
            else:
                kind = "safe" if loss > 0 else "realistic"
                warnings.append(
                    f"A {kind} time frame for this goal is at least {safe_days} days "
                    f"(about {safe_days / DAYS_PER_WEEK:.1f} weeks)."
                )
        return warnings

    def recommend_calories_optimized(self) -> float:
        def objective(calories: float) -> float:
            weight = self._current_weight

            for _ in range(self._time_frame):
                # Metabolic adaptation: maintenance tracks total weight change so far
                # (lower after losing, higher after gaining). It is recomputed from the
                # starting value each day rather than accumulated, so it doesn't compound.
                maintenance = self._maintenance - ADAPT_KCAL_PER_LB * (self._current_weight - weight)
                weight += (calories - maintenance) / KCAL_PER_LB

            return (weight - self._target_weight) ** 2  # Minimize the squared difference

        low, high = self.CALORIE_BOUNDS
        result = minimize_scalar(objective, bounds=(low, high), method="bounded")
        if not result.success:
            logger.warning("Optimization did not converge: %s", result.message)
        # result.fun is the squared miss in lbs; a reachable target is hit almost exactly,
        # so a real miss means the optimum is held back by a calorie bound.
        # safety_warnings() reports this to the user, so it is only logged at INFO
        # (and without the target weight, which is personal data).
        if result.fun > UNREACHABLE_TOLERANCE_LBS**2:
            logger.info(
                "Target is not reachable within %s-%s kcal/day in %d days; recommendation is pinned at the bound",
                low,
                high,
                self._time_frame,
            )
        return float(result.x)
