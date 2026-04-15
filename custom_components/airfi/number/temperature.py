"""Supply air temperature number entity for Airfi air handling unit."""

from __future__ import annotations

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.number import (
    HOLDING_REGISTER_MINIMUM_TEMPERATURE,
    HOLDING_REGISTER_TARGET_TEMPERATURE,
)
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import UnitOfTemperature

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="supply_air_temperature_setting",
        translation_key="supply_air_temperature_setting",
        device_class=NumberDeviceClass.TEMPERATURE,
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

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature in °C."""
        registers: list[int] = self.coordinator.data.get("holding_registers", [])
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
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the number (°C)."""
        return UnitOfTemperature.CELSIUS
