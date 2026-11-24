import pytest

from src.units import (
    KG,
    KG_PER_LB,
    LBS,
    format_weight,
    from_lbs,
    kg_to_lbs,
    lbs_to_kg,
    normalize_unit,
    to_lbs,
)


def test_conversion_factor_is_exact_definition():
    assert KG_PER_LB == 0.45359237
    assert lbs_to_kg(1) == 0.45359237
    assert kg_to_lbs(1) == pytest.approx(2.2046226218487757, rel=1e-15)
    assert lbs_to_kg(200) == pytest.approx(90.718474, rel=1e-15)


@pytest.mark.parametrize("value", [50, 99.9, 150.25, 198.8, 200, 333.3, 600])
def test_round_trip_keeps_precision(value):
    assert kg_to_lbs(lbs_to_kg(value)) == pytest.approx(value, rel=1e-14)
    assert lbs_to_kg(kg_to_lbs(value)) == pytest.approx(value, rel=1e-14)
    assert from_lbs(to_lbs(value, KG), KG) == pytest.approx(value, rel=1e-14)


def test_lbs_is_the_identity():
    assert to_lbs(198.8, LBS) == 198.8
    assert from_lbs(198.8, LBS) == 198.8


@pytest.mark.parametrize("text,unit", [
    ("lbs", LBS), ("LB", LBS), (" pounds ", LBS), ("Pound", LBS),
    ("kg", KG), ("KG", KG), ("kgs", KG), ("kilograms", KG), ("kilo", KG),
])
def test_normalize_unit_accepts_common_spellings(text, unit):
    assert normalize_unit(text) == unit


@pytest.mark.parametrize("text", ["", "stone", "g", "kgg", None])
def test_normalize_unit_rejects_unknown(text):
    with pytest.raises(ValueError, match="unknown weight unit"):
        normalize_unit(text)


def test_format_weight_hides_conversion_noise():
    assert format_weight(kg_to_lbs(90.5), KG) == "90.5 kg"
    assert format_weight(200, LBS) == "200 lbs"
    assert format_weight(200.4, LBS) == "200.4 lbs"
    assert format_weight(200, KG) == "90.72 kg"
    assert format_weight(200, KG, decimals=1) == "90.7 kg"
