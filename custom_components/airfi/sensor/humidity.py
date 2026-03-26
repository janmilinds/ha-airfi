"""Humidity sensor entities for airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.entity import AirfiEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator

INPUT_REGISTER_RELATIVE_HUMIDITY = 23

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="relative_humidity",
        name="Relative humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
)


class AirfiHumiditySensor(SensorEntity, AirfiEntity):
    """Read-only relative humidity sensor backed by input registers."""

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> int | None:
        """Return the current relative humidity in percent."""
        input_registers = self.coordinator.data.get("input_registers", [])
        register_index = INPUT_REGISTER_RELATIVE_HUMIDITY - 1

        if register_index >= len(input_registers):
            return None

        return int(input_registers[register_index])
