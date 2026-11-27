"""Check which unit answers at an address, from what the discovery listener heard."""

from enum import StrEnum

from custom_components.airfi_home.utils.discovery import announced_device_at
from homeassistant.core import HomeAssistant


class AddressIdentity(StrEnum):
    """What is known about the unit at an address."""

    SAME_UNIT = "same_unit"
    OTHER_UNIT = "other_unit"
    UNHEARD = "unheard"


def check_address_identity(hass: HomeAssistant, host: str, serial: str) -> AddressIdentity:
    """
    Compare the serial the unit at this address announced with the one an entry expects.

    The serial is not in the Modbus register map, so only an announcement heard from the address can tell.

    Returns:
        Whether the address announced this serial, another one, or none so far.

    """
    if (device := announced_device_at(hass, host)) is None:
        return AddressIdentity.UNHEARD
    return AddressIdentity.SAME_UNIT if device.unique_key == serial else AddressIdentity.OTHER_UNIT


__all__ = ["AddressIdentity", "check_address_identity"]
