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
    """Convert an Airfi temperature register value into Celsius.

    Modbus registers are unsigned 16-bit (0–65535).  Negative temperatures
    are encoded as standard signed int16 values, so values ≥ 32768 represent
    negative numbers (e.g. 65534 → −2 → −0.2 °C).
    """
    if not math.isfinite(value):
        return 0.0

    raw = int(value) & 0xFFFF
    signed = raw - 0x10000 if raw >= 0x8000 else raw

    return round(signed / 10.0, 1)
