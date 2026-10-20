"""Unit normalization and conversion system (FN-005, RULE-002)."""

import math

LENGTH_CONVERSIONS_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "um": 0.001,
    "micrometer": 0.001,
    "micrometers": 0.001,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
}

ANGLE_CONVERSIONS_TO_DEG: dict[str, float] = {
    "deg": 1.0,
    "degree": 1.0,
    "degrees": 1.0,
    "rad": 180.0 / math.pi,
    "radian": 180.0 / math.pi,
    "radians": 180.0 / math.pi,
}

ROUGHNESS_CONVERSIONS_TO_UM: dict[str, float] = {
    "um": 1.0,
    "ra": 1.0,
    "nm": 0.001,
}


class UnitConversionError(ValueError):
    """Raised when converting between incompatible or unknown units."""


def normalize_unit_str(unit: str) -> str:
    cleaned = unit.strip().lower()
    if cleaned in ("mm", "millimeter", "millimeters"):
        return "mm"
    if cleaned in ("m", "meter", "meters"):
        return "m"
    if cleaned in ("cm", "centimeter", "centimeters"):
        return "cm"
    if cleaned in ("um", "micrometer", "micrometers"):
        return "um"
    if cleaned in ("in", "inch", "inches"):
        return "in"
    if cleaned in ("deg", "degree", "degrees"):
        return "deg"
    if cleaned in ("rad", "radian", "radians"):
        return "rad"
    if cleaned in ("ra",):
        return "ra"
    if cleaned in ("nm",):
        return "nm"
    return cleaned


def convert_unit(value: float, from_unit: str, to_unit: str) -> float:
    norm_from = normalize_unit_str(from_unit)
    norm_to = normalize_unit_str(to_unit)

    if norm_from == norm_to:
        return value

    # Length
    if norm_from in LENGTH_CONVERSIONS_TO_MM and norm_to in LENGTH_CONVERSIONS_TO_MM:
        in_mm = value * LENGTH_CONVERSIONS_TO_MM[norm_from]
        return in_mm / LENGTH_CONVERSIONS_TO_MM[norm_to]

    # Angle
    if norm_from in ANGLE_CONVERSIONS_TO_DEG and norm_to in ANGLE_CONVERSIONS_TO_DEG:
        in_deg = value * ANGLE_CONVERSIONS_TO_DEG[norm_from]
        return in_deg / ANGLE_CONVERSIONS_TO_DEG[norm_to]

    # Roughness
    if norm_from in ROUGHNESS_CONVERSIONS_TO_UM and norm_to in ROUGHNESS_CONVERSIONS_TO_UM:
        in_um = value * ROUGHNESS_CONVERSIONS_TO_UM[norm_from]
        return in_um / ROUGHNESS_CONVERSIONS_TO_UM[norm_to]

    raise UnitConversionError(
        f"Cannot convert between incompatible units: '{from_unit}' and '{to_unit}'"
    )
