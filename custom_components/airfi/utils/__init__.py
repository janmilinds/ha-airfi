"""Utils package for Airfi."""

from homeassistant.helpers.redact import partial_redact


def masked_serial(serial: object) -> str:
    """Return a serial number for a log line: its last four characters, or fully masked when it is short."""
    return partial_redact(str(serial), unmasked_prefix=0, unmasked_suffix=4)


def version_tuple(register_value: int) -> tuple[int, int, int]:
    """Convert a Modbus register value to a semantic version tuple.

    Airfi encodes versions as up to 3-digit integers where each digit
    maps to a version component: ``270`` → ``(2, 7, 0)``.  Values with
    fewer than 3 digits are zero-padded on the right (``15`` → ``(1, 5, 0)``).
    Only the first 3 digits are used; values ≥ 1000 are truncated.
    """
    digits = str(max(0, register_value))[:3]
    parts = [int(d) for d in digits]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def version_string(register_value: int) -> str:
    """Convert a Modbus register value to a version string.

    Example: 270 -> "2.7.0"
    """
    major, minor, patch = version_tuple(register_value)
    return f"{major}.{minor}.{patch}"


__all__ = ["masked_serial", "version_string", "version_tuple"]
