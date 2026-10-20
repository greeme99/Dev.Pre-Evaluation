"""Tests for unit normalization and conversion (FN-005, RULE-002)."""

import pytest

from dev_pre_review.rules.units import UnitConversionError, convert_unit, normalize_unit_str


def test_normalizes_unit_strings() -> None:
    assert normalize_unit_str("MM") == "mm"
    assert normalize_unit_str(" millimeter ") == "mm"
    assert normalize_unit_str("Inches") == "in"
    assert normalize_unit_str("deg") == "deg"
    assert normalize_unit_str("unknown_xyz") == "unknown_xyz"


def test_converts_length_units() -> None:
    # mm to m
    assert convert_unit(1000.0, "mm", "m") == pytest.approx(1.0)
    # m to mm
    assert convert_unit(1.5, "m", "mm") == pytest.approx(1500.0)
    # in to mm
    assert convert_unit(1.0, "in", "mm") == pytest.approx(25.4)
    # um to mm
    assert convert_unit(50.0, "um", "mm") == pytest.approx(0.05)


def test_converts_angle_units() -> None:
    import math

    assert convert_unit(180.0, "deg", "rad") == pytest.approx(math.pi)
    assert convert_unit(math.pi, "rad", "deg") == pytest.approx(180.0)


def test_rejects_incompatible_unit_conversion() -> None:
    with pytest.raises(UnitConversionError):
        convert_unit(10.0, "mm", "deg")

    with pytest.raises(UnitConversionError):
        convert_unit(10.0, "mm", "unknown_unit")
