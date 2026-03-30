"""Shared mapping from integration exceptions to user-facing form errors."""

from __future__ import annotations

from custom_components.airfi.api import AirfiApiClientConnectionError, AirfiApiClientModbusError


def map_connection_exception_to_error(exception: Exception) -> str:
    """Map connection validation exceptions to form error keys."""
    if isinstance(exception, AirfiApiClientModbusError):
        return "cannot_retrieve_data"

    if isinstance(exception, AirfiApiClientConnectionError):
        return "cannot_connect"

    return "cannot_connect"
