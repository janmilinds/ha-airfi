"""Binary sensor platform for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntityDescription

from .connectivity import ENTITY_DESCRIPTIONS as CONNECTIVITY_DESCRIPTIONS, AirfiConnectivitySensor

# Read-only platform — no limit on concurrent entity updates
PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from custom_components.airfi.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Combine all entity descriptions from different modules
ENTITY_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (*CONNECTIVITY_DESCRIPTIONS,)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        AirfiConnectivitySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in CONNECTIVITY_DESCRIPTIONS
    )
