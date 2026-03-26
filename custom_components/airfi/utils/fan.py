"""Fan register address constants for airfi."""

from __future__ import annotations

HOLDING_REGISTER_FAN_SPEED = 1
"""Modbus holding register address for fan rotation speed (4x00001).

Device values: 1-5, where 1 = slowest and 5 = fastest.
"""
