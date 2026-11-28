"""Connection validators for config flow."""

from typing import TYPE_CHECKING

from custom_components.airfi_home.api import AirfiApiClient, AirfiApiClientError
from custom_components.airfi_home.const import DEFAULT_MODBUS_PORT, LOGGER
from custom_components.airfi_home.coordinator.feature_manager import AirfiDeviceError, AirfiFeatureManager
from custom_components.airfi_home.utils.error_mapping import map_connection_exception_to_error

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def validate_connection(hass: HomeAssistant, host: str, unit_id: int) -> None:
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


async def connection_error(hass: HomeAssistant, host: str, unit_id: int) -> str | None:
    """
    Check the unit at the address and Modbus ID, for a form.

    Returns:
        The form error key for a unit that cannot be used, or None when it answers and is supported.

    """
    try:
        await validate_connection(hass, host, unit_id)
    except (AirfiApiClientError, AirfiDeviceError) as exception:
        LOGGER.warning("Unit at %s did not pass the check: %s", host, exception)
        return map_connection_exception_to_error(exception)
    return None


__all__ = [
    "connection_error",
    "validate_connection",
]
