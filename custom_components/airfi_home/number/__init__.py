"""Number platform for Airfi."""

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntityDescription

from .boost import ENTITY_DESCRIPTIONS as BOOST_DESCRIPTIONS, AirfiBoostIncreaseNumber
from .temperature import ENTITY_DESCRIPTIONS as TEMPERATURE_DESCRIPTIONS, AirfiTemperatureNumber

if TYPE_CHECKING:
    from custom_components.airfi_home.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

PARALLEL_UPDATES = 1

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (*BOOST_DESCRIPTIONS, *TEMPERATURE_DESCRIPTIONS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform; the boost increase needs register map 2.9 or newer."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        AirfiTemperatureNumber(coordinator=coordinator, entity_description=entity_description)
        for entity_description in TEMPERATURE_DESCRIPTIONS
    )
    if coordinator.feature_manager.has_feature("boost"):
        async_add_entities(
            AirfiBoostIncreaseNumber(coordinator=coordinator, entity_description=desc) for desc in BOOST_DESCRIPTIONS
        )
