"""Fan register address constants for airfi."""

from __future__ import annotations

HOLDING_REGISTER_FAN_SPEED = 1
"""Modbus holding register address for fan rotation speed (4x00001).

Device values: 1-5, where 1 = slowest and 5 = fastest.
"""

HOLDING_REGISTER_FAN_ACTIVE = 12
"""Modbus holding register address for fan active state (4x00012).

Device values: 0 = at-home (active), 1 = away (inactive).
Device autonomously manages fan speed: away→minimum, at-home→previous speed.
"""
