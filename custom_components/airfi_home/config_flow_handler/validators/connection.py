"""Connection validators for config flow."""

from typing import TYPE_CHECKING

from custom_components.airfi_home.api import AirfiApiClient
from custom_components.airfi_home.const import DEFAULT_MODBUS_ID, DEFAULT_MODBUS_PORT
from custom_components.airfi_home.coordinator.feature_manager import AirfiFeatureManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def validate_connection(hass: HomeAssistant, host: str, unit_id: int = DEFAULT_MODBUS_ID) -> None:
    """
    Check that a unit this integration supports answers at the address, to this Modbus ID.

    The request is sent once, so a unit that does not answer is reported within the client's timeout.

    Raises:
        AirfiApiClientConnectionError: If no connection opens at the address.
        AirfiApiClientNoResponseError: If the connection opens but the unit does not answer this Modbus ID.
        AirfiApiClientError: If the unit's answer cannot be read.
        AirfiDeviceError: If the unit's software is not supported, or its version registers are incomplete.

    """
    del hass
    client = AirfiApiClient(
        host=host,
        port=DEFAULT_MODBUS_PORT,
        unit_id=unit_id,
        retries=0,
    )
    AirfiFeatureManager.check_supported(await client.async_get_lookup_registers())


__all__ = [
    "validate_connection",
]
