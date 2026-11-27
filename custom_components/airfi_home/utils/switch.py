"""Switch register address constants for Airfi."""

HOLDING_REGISTER_BOOSTED_COOLING = 51
"""Modbus holding register address for boosted cooling (4x00051).

Device values: 0 = off, 1 = on.
Requires Modbus map version >= 2.1.0.
"""

HOLDING_REGISTER_SAUNA_FUNCTION = 57
"""Modbus holding register address for sauna function (4x00057).

Device values: 0 = off, 1 = on.
Requires Modbus map version >= 2.5.0.
"""

HOLDING_REGISTER_FIREPLACE_FUNCTION = 58
"""Modbus holding register address for fireplace function (4x00058).

Device values: 0 = off, 1 = on.
Requires Modbus map version >= 2.5.0.
"""
