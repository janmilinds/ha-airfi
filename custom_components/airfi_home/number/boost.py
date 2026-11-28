"""Boost increase number entity for Airfi."""

from custom_components.airfi_home.entity import AirfiEntity
from custom_components.airfi_home.utils.boost import HOLDING_REGISTER_BOOST_SPEED
from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory, UnitOfRatio

ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="boost_increase",
        translation_key="boost_increase",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
    ),
)


class AirfiBoostIncreaseNumber(NumberEntity, AirfiEntity):
    """How much a boost raises the fan speeds relative to their current speed, from holding register 63 (4x00063)."""

    @property
    def native_value(self) -> int | None:
        """Return the boost increase in percent."""
        return self.coordinator.data.holding_register(HOLDING_REGISTER_BOOST_SPEED)

    async def async_set_native_value(self, value: float) -> None:
        """Write the boost increase in whole percent."""
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_BOOST_SPEED, round(value))
        await self.coordinator.async_request_refresh()
