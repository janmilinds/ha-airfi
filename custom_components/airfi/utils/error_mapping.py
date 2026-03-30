"""Shared mapping from integration exceptions to user-facing form errors."""

from __future__ import annotations

CONNECTION_ERROR_MAP = {
    "AirfiApiClientConnectionError": "cannot_connect",
    "AirfiApiClientModbusError": "cannot_retrieve_data",
}


def map_connection_exception_to_error(exception: Exception) -> str:
    """Map connection validation exceptions to form error keys."""
    return CONNECTION_ERROR_MAP.get(type(exception).__name__, "cannot_connect")
