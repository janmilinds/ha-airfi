"""Switch entities for Airfi special functions (sauna, fireplace, boosted cooling)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from custom_components.airfi.entity import AirfiEntity
from custom_components.airfi.utils.switch import (
    HOLDING_REGISTER_BOOSTED_COOLING,
    HOLDING_REGISTER_FIREPLACE_FUNCTION,
    HOLDING_REGISTER_SAUNA_FUNCTION,
)
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AirfiSwitchEntityDescription(SwitchEntityDescription):
    """Extended switch description with Modbus register address and feature flag."""

    register_address: int
    feature_flag: str


ENTITY_DESCRIPTIONS: tuple[AirfiSwitchEntityDescription, ...] = (
    AirfiSwitchEntityDescription(
        key="fireplace_function",
        translation_key="fireplace_function",
        register_address=HOLDING_REGISTER_FIREPLACE_FUNCTION,
        feature_flag="fireplace_function",
        entity_registry_enabled_default=False,
    ),
    AirfiSwitchEntityDescription(
        key="sauna_function",
        translation_key="sauna_function",
        register_address=HOLDING_REGISTER_SAUNA_FUNCTION,
        feature_flag="sauna_function",
        entity_registry_enabled_default=False,
    ),
    AirfiSwitchEntityDescription(
        key="boosted_cooling",
        translation_key="boosted_cooling",
        register_address=HOLDING_REGISTER_BOOSTED_COOLING,
        feature_flag="boosted_cooling",
        entity_registry_enabled_default=False,
    ),
)


class AirfiFunctionSwitch(SwitchEntity, AirfiEntity):
    """On/off switch backed by a single holding register (0/1).

    Each switch controls a special ventilation function (sauna, fireplace,
    boosted cooling) via a dedicated Modbus holding register.

    Uses optimistic state updates: writes the expected value to HA immediately
    after the Modbus write succeeds, then requests a coordinator refresh to
    confirm. This prevents the UI from briefly bouncing back to the old state.
    """

    entity_description: AirfiSwitchEntityDescription

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: AirfiSwitchEntityDescription,
    ) -> None:
        """Initialize with no optimistic state."""
        super().__init__(coordinator, entity_description)
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool | None:
        """Return True if the function is active."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        registers: list[int] = self.coordinator.data.get("holding_registers", [])
        index = self.entity_description.register_address - 1
        if index >= len(registers):
            return None
        return registers[index] == 1

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when real data arrives from coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the function."""
        await self.coordinator.async_set_holding_register(self.entity_description.register_address, 1)
        self._optimistic_state = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate the function."""
        await self.coordinator.async_set_holding_register(self.entity_description.register_address, 0)
        self._optimistic_state = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
