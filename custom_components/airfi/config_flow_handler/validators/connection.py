"""Connection validators for config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.api import AirfiApiClient
from custom_components.airfi.const import DEFAULT_MODBUS_PORT

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def validate_connection(hass: HomeAssistant, host: str) -> None:
    """Validate host by testing Modbus connection."""
    del hass
    client = AirfiApiClient(
        host=host,
        port=DEFAULT_MODBUS_PORT,
    )
    await client.async_test_connection()


__all__ = [
    "validate_connection",
]
