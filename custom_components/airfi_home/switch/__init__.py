"""Switch platform for Airfi."""

from typing import TYPE_CHECKING

from custom_components.airfi_home.const import PARALLEL_UPDATES as PARALLEL_UPDATES

from .functions import ENTITY_DESCRIPTIONS as FUNCTION_DESCRIPTIONS, AirfiFunctionSwitch

if TYPE_CHECKING:
    from custom_components.airfi_home.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform.

    Only creates entities whose feature flag is supported by the device's
    Modbus register map version.
    """
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        AirfiFunctionSwitch(
            coordinator=coordinator,
            entity_description=desc,
        )
        for desc in FUNCTION_DESCRIPTIONS
        if coordinator.feature_manager.has_feature(desc.feature_flag)
    )
