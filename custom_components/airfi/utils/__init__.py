"""Utils package for Airfi."""

from __future__ import annotations


def version_tuple(register_value: int) -> tuple[int, int, int]:
    """Convert a Modbus register value to a semantic version tuple.

    Example: 270 -> (2, 7, 0)
    """
    digits = str(max(0, register_value))
    if len(digits) >= 3:
        return int(digits[0]), int(digits[1]), int(digits[2])
    if len(digits) == 2:
        return int(digits[0]), int(digits[1]), 0
    return int(digits[0]), 0, 0


def version_string(register_value: int) -> str:
    """Convert a Modbus register value to a version string.

    Example: 270 -> "2.7.0"
    """
    major, minor, patch = version_tuple(register_value)
    return f"{major}.{minor}.{patch}"


__all__ = ["version_string", "version_tuple"]
