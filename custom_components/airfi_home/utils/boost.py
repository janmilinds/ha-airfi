"""Boost register addresses and the remaining boost time for Airfi."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.airfi_home.coordinator.data_processing import AirfiDeviceData

HOLDING_REGISTER_BOOST_TIME = 62
"""Modbus holding register address for the boost time (4x00062).

Writing N minutes (0–120) starts a boost that counts down once a minute; writing 0 stops it.
Requires Modbus map version >= 2.9.0.
"""

HOLDING_REGISTER_BOOST_SPEED = 63
"""Modbus holding register address for the boost speed (4x00063), 0–100 %.

Requires Modbus map version >= 2.9.0.
"""

BOOST_DURATIONS_MINUTES: tuple[int, ...] = (30, 60, 90, 120)


def boost_remaining_minutes(data: AirfiDeviceData) -> int | None:
    """Return the minutes left in a running boost, 0 when none runs, or None when the unit did not report it."""
    return data.holding_register(HOLDING_REGISTER_BOOST_TIME)
