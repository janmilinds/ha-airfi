"""Temperature sensor entities for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.temperature import (
    INPUT_REGISTER_EXHAUST_AIR_TEMP,
    INPUT_REGISTER_EXTRACT_AIR_TEMP,
    INPUT_REGISTER_OUTDOOR_AIR_TEMP,
    INPUT_REGISTER_SUPPLY_AIR_TEMP,
    convert_temperature,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import UnitOfTemperature

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator


ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outdoor_air_temperature",
        translation_key="outdoor_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="extract_air_temperature",
        translation_key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="exhaust_air_temperature",
        translation_key="exhaust_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="supply_air_temperature",
        translation_key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
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
        input_registers = self.coordinator.data.input_registers
        register_index = register_address - 1

        if register_index >= len(input_registers):
            return None

        return convert_temperature(input_registers[register_index])
