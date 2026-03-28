"""Fan entity for Airfi air handling unit."""

from __future__ import annotations

import math
from typing import Any

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.fan import HOLDING_REGISTER_FAN_ACTIVE, HOLDING_REGISTER_FAN_SPEED
from homeassistant.components.fan import FanEntity, FanEntityDescription, FanEntityFeature
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

# Speed range for percentage calculations: device supports 1-5, map to 20-100%
SPEED_RANGE = (1, 5)

ENTITY_DESCRIPTIONS: tuple[FanEntityDescription, ...] = (
    FanEntityDescription(
        key="fan",
        name="Fan",
        icon="mdi:fan",
    ),
)


class AirfiFan(FanEntity, AirfiEntity):
    """Fan entity combining on/off state and speed control.

    At-home/away mode controls power: away mode (register 12 = 1) reduces to minimum speed,
    at-home mode (register 12 = 0) restores previous speed. Speed is independently controlled
    via register 1 (device values 1-5 map to HA percentages 20-100).
    """

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    _attr_speed_count = 5  # Device supports 5 speed levels

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is in at-home mode (on).

        Device value 0 (register 12) = at-home (on), device value 1 = away (off).
        """
        registers: list[int] = self.coordinator.data.get("holding_registers", [])
        index = HOLDING_REGISTER_FAN_ACTIVE - 1
        if index >= len(registers):
            return None
        return registers[index] == 0

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed as a percentage (20-100).

        Maps device values 1-5 to HA percentages 20-100 (step 20).
        """
        if self.is_on is False:
            return 0
        registers: list[int] = self.coordinator.data.get("holding_registers", [])
        index = HOLDING_REGISTER_FAN_SPEED - 1
        if index >= len(registers):
            return None
        device_speed = registers[index]
        return ranged_value_to_percentage(SPEED_RANGE, device_speed)

    @property
    def icon(self) -> str:
        """Return icon based on on/off state."""
        if self.is_on is True:
            return "mdi:fan"
        if self.is_on is False:
            return "mdi:fan-off"
        return "mdi:fan"

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on (set at-home mode, device value 0 to register 12)."""
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_FAN_ACTIVE, 0)
        if percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off (set away mode, device value 1 to register 12)."""
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_FAN_ACTIVE, 1)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage (20-100, maps to device 1-5)."""
        if percentage == 0:
            await self.async_turn_off()
            return
        # Ensure fan is on before setting speed
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_FAN_ACTIVE, 0)
        # Convert percentage to device value 1-5
        device_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_FAN_SPEED, device_speed)
