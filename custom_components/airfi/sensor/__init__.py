"""Sensor platform for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.const import PARALLEL_UPDATES as PARALLEL_UPDATES
from homeassistant.components.sensor import SensorEntityDescription

from .humidity import ENTITY_DESCRIPTIONS as HUMIDITY_DESCRIPTIONS, AirfiHumiditySensor
from .temperature import ENTITY_DESCRIPTIONS as TEMPERATURE_DESCRIPTIONS, AirfiTemperatureSensor

if TYPE_CHECKING:
    from custom_components.airfi.data import AirfiConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    *HUMIDITY_DESCRIPTIONS,
    *TEMPERATURE_DESCRIPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        AirfiHumiditySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in HUMIDITY_DESCRIPTIONS
    )
    async_add_entities(
        AirfiTemperatureSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in TEMPERATURE_DESCRIPTIONS
    )
