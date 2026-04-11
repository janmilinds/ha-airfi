"""Number register address constants for Airfi."""

from __future__ import annotations

HOLDING_REGISTER_TARGET_TEMPERATURE = 5
"""Modbus holding register address for target supply air temperature (4x00005).

Device values: temperature in °C × 10 (e.g. 200 = 20.0 °C).
Range: 130–250 (13.0 °C – 25.0 °C), step 10 (1.0 °C).
"""

HOLDING_REGISTER_MINIMUM_TEMPERATURE = 50
"""Modbus holding register address for minimum temperature / bypass (4x00050).

Device values: temperature in °C (not scaled).
Requires Modbus map version >= 2.1.0 (feature ``minimum_temperature_set``).
"""
