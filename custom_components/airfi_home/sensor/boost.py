"""Boost end time sensor entity for Airfi."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from custom_components.airfi_home.entity import AirfiEntity
from custom_components.airfi_home.utils.boost import boost_remaining_minutes
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.airfi_home.coordinator import AirfiDataUpdateCoordinator

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="boost_end",
        translation_key="boost_end",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

END_TIME_TOLERANCE = timedelta(seconds=90)


class AirfiBoostEndSensor(SensorEntity, AirfiEntity):
    """When the running boost ends, or unknown when no boost runs.

    The unit reports the remaining time in whole minutes, so the end time computed on each poll wanders by up to a
    minute. The sensor keeps its end time until a poll moves it by more than END_TIME_TOLERANCE, which only a new or
    changed boost does, so the state does not change on every poll.
    """

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the end time from the current data."""
        super().__init__(coordinator, entity_description)
        self._end: datetime | None = None
        self._update_end()

    @property
    def native_value(self) -> datetime | None:
        """Return the end time of the running boost."""
        return self._end

    def _handle_coordinator_update(self) -> None:
        """Recompute the end time when new data arrives from the coordinator."""
        self._update_end()
        super()._handle_coordinator_update()

    def _update_end(self) -> None:
        minutes = boost_remaining_minutes(self.coordinator.data)
        if not minutes:
            self._end = None
            return
        end = dt_util.utcnow().replace(microsecond=0) + timedelta(minutes=minutes)
        if self._end is None or abs(end - self._end) > END_TIME_TOLERANCE:
            self._end = end
