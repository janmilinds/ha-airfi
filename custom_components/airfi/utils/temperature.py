"""Temperature register constants and conversion helpers for Airfi."""

from __future__ import annotations

import math

INPUT_REGISTER_OUTDOOR_AIR_TEMP = 4
"""Modbus input register address for outdoor air temperature (3x00004)."""

INPUT_REGISTER_EXTRACT_AIR_TEMP = 6
"""Modbus input register address for extract air temperature (3x00006)."""

INPUT_REGISTER_EXHAUST_AIR_TEMP = 7
"""Modbus input register address for exhaust air temperature (3x00007)."""

INPUT_REGISTER_SUPPLY_AIR_TEMP = 8
"""Modbus input register address for supply air temperature (3x00008)."""


def convert_temperature(value: float) -> float:
    """Convert an Airfi temperature register value into Celsius."""
    if not math.isfinite(value):
        return 0.0

    converted = value

    # Keep parity with Homebridge conversion for signed 16-bit encoded values.
    if converted > 62803:
        converted = value - 65535

    return round(converted / 10.0, 1)
