"""Temperature sensor entities for Airfi."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from custom_components.airfi.entity import AirfiEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTemperature

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator

INPUT_REGISTER_OUTDOOR_AIR_TEMP = 4
INPUT_REGISTER_EXTRACT_AIR_TEMP = 6
INPUT_REGISTER_EXHAUST_AIR_TEMP = 7
INPUT_REGISTER_SUPPLY_AIR_TEMP = 8


def convert_temperature(value: float) -> float:
    """Convert an Airfi temperature register value into Celsius."""
    if not math.isfinite(value):
        return 0.0

    converted = value

    # Keep parity with Homebridge conversion for signed 16-bit encoded values.
    if converted > 62803:
        converted = value - 65535

    return round(converted / 10.0, 1)


ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outdoor_air_temperature",
        name="Outdoor air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="extract_air_temperature",
        name="Extract air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="exhaust_air_temperature",
        name="Exhaust air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="supply_air_temperature",
        name="Supply air",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
)

REGISTER_ADDRESS_BY_KEY: dict[str, int] = {
    "outdoor_air_temperature": INPUT_REGISTER_OUTDOOR_AIR_TEMP,
    "extract_air_temperature": INPUT_REGISTER_EXTRACT_AIR_TEMP,
    "exhaust_air_temperature": INPUT_REGISTER_EXHAUST_AIR_TEMP,
    "supply_air_temperature": INPUT_REGISTER_SUPPLY_AIR_TEMP,
}


class AirfiTemperatureSensor(SensorEntity, AirfiEntity):
    """Read-only temperature sensor backed by input registers."""

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float | None:
        """Return the current temperature value in Celsius."""
        register_address = REGISTER_ADDRESS_BY_KEY[self.entity_description.key]
        input_registers = self.coordinator.data.get("input_registers", [])
        register_index = register_address - 1

        if register_index >= len(input_registers):
            return None

        return convert_temperature(input_registers[register_index])
