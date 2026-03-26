"""Fan speed number entity for airfi."""

from __future__ import annotations

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.fan import HOLDING_REGISTER_FAN_SPEED
from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="fan_speed",
        name="Fan speed",
        icon="mdi:fan",
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.SLIDER,
    ),
)


class AirfiFanSpeedNumber(NumberEntity, AirfiEntity):
    """Fan speed number entity for the Airfi air handling unit.

    Renders as a 5-step slider (device values 1–5) in the Home Assistant UI.
    """

    @property
    def native_value(self) -> float | None:
        """Return the current fan speed as a device value (1–5)."""
        registers: list[int] = self.coordinator.data.get("holding_registers", [])
        index = HOLDING_REGISTER_FAN_SPEED - 1
        if index >= len(registers):
            return None
        return float(registers[index])

    async def async_set_native_value(self, value: float) -> None:
        """Write the chosen fan speed (1–5) to the device."""
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_FAN_SPEED, int(value))
