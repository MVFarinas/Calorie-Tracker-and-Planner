"""Weight unit conversion.

Weights are always stored in pounds inside the program (and in the saved log);
these helpers convert to and from the unit the user has chosen for display.
"""

LBS = "lbs"
KG = "kg"
UNITS = (LBS, KG)

# Exact by definition (international avoirdupois pound).
KG_PER_LB = 0.45359237

# Spellings accepted by normalize_unit, e.g. from a "unit" column in a file.
_ALIASES = {
    "lb": LBS,
    "lbs": LBS,
    "pound": LBS,
    "pounds": LBS,
    "kg": KG,
    "kgs": KG,
    "kilo": KG,
    "kilos": KG,
    "kilogram": KG,
    "kilograms": KG,
}


def normalize_unit(value) -> str:
    """LBS or KG for any accepted spelling (case-insensitive); raises ValueError otherwise."""
    unit = _ALIASES.get(str(value).strip().lower())
    if unit is None:
        raise ValueError(f"unknown weight unit {value!r} (use 'lbs' or 'kg')")
    return unit


def lbs_to_kg(lbs: float) -> float:
    return lbs * KG_PER_LB


def kg_to_lbs(kg: float) -> float:
    return kg / KG_PER_LB


def to_lbs(value: float, unit: str) -> float:
    """Convert a weight given in `unit` to pounds."""
    return kg_to_lbs(value) if normalize_unit(unit) == KG else value


def from_lbs(lbs: float, unit: str) -> float:
    """Convert a weight in pounds to `unit`."""
    return lbs_to_kg(lbs) if normalize_unit(unit) == KG else lbs


def format_weight(lbs: float, unit: str, decimals: int = 2) -> str:
    """A weight stored in pounds, shown in `unit` without trailing zeros, e.g. '90.5 kg'.
    Rounding hides conversion noise such as 90.49999999999999."""
    value = round(from_lbs(lbs, unit), decimals)
    return f"{value:g} {normalize_unit(unit)}"
