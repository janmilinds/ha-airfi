"""
Error handling utilities for the coordinator.

This module centralises error classification and logging decisions so that
coordinator/base.py stays focused on data fetching and recovery flow.

Current responsibilities:
- Classifying whether a connection error warrants a rediscovery attempt
- Logging Modbus failures at the appropriate severity

Planned future responsibilities (not yet implemented):
- Graceful degradation via handle_partial_data when register groups are
  fetched independently and a partial result is available
"""

from __future__ import annotations

from custom_components.airfi.api import AirfiApiClientConnectionError
from custom_components.airfi.const import LOGGER


def should_try_rediscovery(exception: Exception) -> bool:
    """Return True if the error warrants a rediscovery attempt.

    Rediscovery is only useful when the device is unreachable at the TCP
    level — the device may have changed IP address. Modbus protocol errors
    indicate the device is reachable, so rediscovery would not help.

    Args:
        exception: The exception raised by the API client.

    Returns:
        True if rediscovery should be attempted, False otherwise.

    Example:
        >>> from custom_components.airfi.api import AirfiApiClientConnectionError
        >>> should_try_rediscovery(AirfiApiClientConnectionError("timeout"))
        True
        >>> from custom_components.airfi.api import AirfiApiClientModbusError
        >>> should_try_rediscovery(AirfiApiClientModbusError("bad response"))
        False
    """
    return isinstance(exception, AirfiApiClientConnectionError)


def log_modbus_failure(exception: Exception, context: str) -> None:
    """Log a Modbus communication failure with context.

    Uses debug level — Home Assistant already surfaces coordinator update
    failures to the user via UpdateFailed, so additional warning/error
    logging here would be duplicative and noisy.

    Args:
        exception: The exception that caused the failure.
        context: Short description of what was being attempted, e.g.
                 "initial fetch" or "post-rediscovery fetch".

    Example:
        >>> log_modbus_failure(exception, "initial fetch")
    """
    LOGGER.debug("Modbus failure during %s: %s", context, exception)
