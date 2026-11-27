"""
Base entity class for Airfi.

This module provides the base entity class that all integration entities inherit from.
It handles common functionality like device info, unique IDs, and coordinator integration.

For more information on entities:
https://developers.home-assistant.io/docs/core/entity
https://developers.home-assistant.io/docs/core/entity/index/#common-properties
"""

from typing import TYPE_CHECKING

from custom_components.airfi_home.const import ATTRIBUTION, CONF_MODEL_NAME
from custom_components.airfi_home.coordinator import AirfiDataUpdateCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from homeassistant.helpers.entity import EntityDescription


class AirfiEntity(CoordinatorEntity[AirfiDataUpdateCoordinator]):
    """
    Base entity class for Airfi.

    All entities in this integration inherit from this class, which provides:
    - Automatic coordinator updates
    - Device info management
    - Unique ID generation
    - Attribution and naming conventions

    For more information:
    https://developers.home-assistant.io/docs/core/entity
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirfiDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """
        Initialize the base entity.

        Args:
            coordinator: The data update coordinator for this entity.
            entity_description: The entity description defining characteristics.

        """
        super().__init__(coordinator)
        self.entity_description = entity_description
        serial = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(coordinator.config_entry.domain, serial)},
            name=coordinator.config_entry.title,
            manufacturer="Airfi",
            model=coordinator.config_entry.data.get(CONF_MODEL_NAME, "Airfi"),
            serial_number=serial,
            hw_version=coordinator.hw_version or None,
            sw_version=coordinator.data.firmware_version if coordinator.data else "Unknown",
        )
