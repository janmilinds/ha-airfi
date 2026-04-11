"""Number platform for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.const import PARALLEL_UPDATES as PARALLEL_UPDATES
from homeassistant.components.number import NumberEntityDescription

from .temperature import ENTITY_DESCRIPTIONS as TEMPERATURE_DESCRIPTIONS, AirfiTemperatureNumber

if TYPE_CHECKING:
    from custom_components.airfi.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (*TEMPERATURE_DESCRIPTIONS,)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    async_add_entities(
        AirfiTemperatureNumber(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in TEMPERATURE_DESCRIPTIONS
    )
