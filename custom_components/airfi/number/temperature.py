"""Supply air temperature number entity for Airfi air handling unit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.number import (
    HOLDING_REGISTER_MINIMUM_TEMPERATURE,
    HOLDING_REGISTER_TARGET_TEMPERATURE,
)
from custom_components.airfi.utils.temperature import INPUT_REGISTER_SUPPLY_AIR_TEMP, convert_temperature
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import UnitOfTemperature

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="supply_air_temperature_setting",
        translation_key="supply_air_temperature_setting",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=13.0,
        native_max_value=25.0,
        native_step=1.0,
        mode=NumberMode.BOX,
    ),
)


class AirfiTemperatureNumber(NumberEntity, AirfiEntity):
    """Supply air target temperature control.

    Reads/writes holding register 5 (4x00005).
    Device stores the value as °C × 10 (e.g. 200 = 20.0 °C).

    When the ``minimum_temperature_set`` feature is available (modbus >= 2.1.0),
    also writes holding register 50 (4x00050) with the raw °C value so the two
    settings stay in parity.
    """

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature in °C."""
        registers: list[int] = self.coordinator.data.holding_registers
        index = HOLDING_REGISTER_TARGET_TEMPERATURE - 1
        if index >= len(registers):
            return None
        raw = registers[index]
        return round(raw / 10.0, 1)

    async def async_set_native_value(self, value: float) -> None:
        """Set the supply air temperature (°C, written as value × 10)."""
        device_value = int(round(value * 10))
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_TARGET_TEMPERATURE, device_value)

        if self.coordinator.feature_manager.has_feature("minimum_temperature_set"):
            await self.coordinator.async_set_holding_register(
                HOLDING_REGISTER_MINIMUM_TEMPERATURE,
                int(round(value)),
            )

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, float | str | None]:
        """Return additional attributes including current measured supply-air temperature.

        Some Lovelace components read `supply_air_temperature` from entity attributes
        to show the measured temperature alongside a setpoint control.
        """
        input_registers: list[int] = self.coordinator.data.input_registers
        index = INPUT_REGISTER_SUPPLY_AIR_TEMP - 1
        if index >= len(input_registers):
            return {}

        value = convert_temperature(input_registers[index])

        return {
            "supply_air_temperature": value,
        }
