"""Diagnostic sensor entities for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.entity import AirfiEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

if TYPE_CHECKING:
    from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="firmware_version",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="modbus_register_version",
        translation_key="modbus_register_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


class AirfiDiagnosticSensor(SensorEntity, AirfiEntity):
    """Diagnostic sensor that reads a string value from coordinator data."""

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> str | None:
        """Return the diagnostic value from coordinator data."""
        return getattr(self.coordinator.data, self.entity_description.key, None)
