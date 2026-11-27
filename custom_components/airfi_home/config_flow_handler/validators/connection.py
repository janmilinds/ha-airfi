"""Connection validators for config flow."""

from typing import TYPE_CHECKING

from custom_components.airfi_home.api import AirfiApiClient
from custom_components.airfi_home.const import DEFAULT_MODBUS_PORT
from custom_components.airfi_home.coordinator.feature_manager import AirfiFeatureManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def validate_connection(hass: HomeAssistant, host: str) -> None:
    """
    Check that a unit this integration supports answers at the address.

    Raises:
        AirfiApiClientError: If nothing answers over Modbus at the address.
        AirfiDeviceError: If the unit's software is not supported, or its version registers are incomplete.

    """
    del hass
    client = AirfiApiClient(
        host=host,
        port=DEFAULT_MODBUS_PORT,
    )
    AirfiFeatureManager.check_supported(await client.async_get_lookup_registers())


__all__ = [
    "validate_connection",
]
