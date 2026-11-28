"""Boost timer select entity for Airfi."""

from custom_components.airfi_home.entity import AirfiEntity
from custom_components.airfi_home.utils.boost import (
    BOOST_DURATIONS_MINUTES,
    HOLDING_REGISTER_BOOST_TIME,
    boost_remaining_minutes,
)
from homeassistant.components.select import SelectEntity, SelectEntityDescription

BOOST_OFF = "0"
OPTIONS: list[str] = [BOOST_OFF, *(str(minutes) for minutes in BOOST_DURATIONS_MINUTES)]

ENTITY_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="boost_timer",
        translation_key="boost_timer",
        options=OPTIONS,
    ),
)


def option_for_remaining(minutes: int) -> str:
    """Return the shortest option that covers the remaining boost time."""
    if minutes <= 0:
        return BOOST_OFF
    return str(
        next((duration for duration in BOOST_DURATIONS_MINUTES if minutes <= duration), BOOST_DURATIONS_MINUTES[-1])
    )


class AirfiBoostTimeSelect(SelectEntity, AirfiEntity):
    """Start, extend or stop a timed boost; the state is the remaining time rounded up to a whole option."""

    _optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the option matching the remaining boost time."""
        if self._optimistic_option is not None:
            return self._optimistic_option
        minutes = boost_remaining_minutes(self.coordinator.data)
        if minutes is None:
            return None
        return option_for_remaining(minutes)

    def _handle_coordinator_update(self) -> None:
        """Clear the optimistic option when real data arrives from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Start a boost for the chosen number of minutes, or stop it with 0."""
        await self.coordinator.async_set_holding_register(HOLDING_REGISTER_BOOST_TIME, int(option))
        self._optimistic_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
