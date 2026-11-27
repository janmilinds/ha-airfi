"""Select platform for Airfi."""

from typing import TYPE_CHECKING

from .boost import ENTITY_DESCRIPTIONS as BOOST_DESCRIPTIONS, AirfiBoostTimeSelect

if TYPE_CHECKING:
    from custom_components.airfi_home.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform; the boost needs register map 2.9 or newer."""
    coordinator = entry.runtime_data.coordinator
    if not coordinator.feature_manager.has_feature("boost"):
        return
    async_add_entities(
        AirfiBoostTimeSelect(coordinator=coordinator, entity_description=desc) for desc in BOOST_DESCRIPTIONS
    )
