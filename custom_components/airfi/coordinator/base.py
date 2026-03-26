"""
Core DataUpdateCoordinator implementation for airfi.

This module contains the main coordinator class that manages data fetching
and updates for all entities in the integration. It handles refresh cycles,
error handling, and triggers reauthentication when needed.

For more information on coordinators:
https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.airfi.api import AirfiApiClientAuthenticationError, AirfiApiClientError
from custom_components.airfi.const import CONF_SERIAL_NUMBER, LOGGER
from custom_components.airfi.coordinator.data_processing import parse_device_data, to_coordinator_payload
from custom_components.airfi.coordinator.feature_manager import AirfiFeatureManager
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from custom_components.airfi.data import AirfiConfigEntry


class AirfiDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching data from the API.

    This coordinator handles all data fetching for the integration and distributes
    updates to all entities. It manages:
    - Periodic data updates based on update_interval
    - Error handling and recovery
    - Authentication failure detection and reauthentication triggers
    - Data distribution to all entities
    - Context-based data fetching (only fetch data for active entities)

    For more information:
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities

    Attributes:
        config_entry: The config entry for this integration instance.
    """

    config_entry: AirfiConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(*args, **kwargs)
        self.feature_manager = AirfiFeatureManager()
        self.input_registers: int = 0
        self.holding_registers: int = 0

    async def _async_setup(self) -> None:
        """
        Set up the coordinator.

        This method is called automatically during async_config_entry_first_refresh()
        and is the ideal place for one-time initialization tasks such as:
        - Loading device information
        - Setting up event listeners
        - Initializing caches

        This runs before the first data fetch, ensuring any required setup
        is complete before entities start requesting data.
        """
        try:
            # Fetch lookup registers to validate firmware and get register counts
            device_name = f"Airfi {self.config_entry.data.get(CONF_SERIAL_NUMBER, 'Unknown')}"
            lookup_registers = await self.config_entry.runtime_data.client.async_get_lookup_registers()

            # Initialize feature manager and validate firmware
            self.feature_manager.initialize(device_name, lookup_registers)

            # Get register counts based on firmware version
            self.input_registers, self.holding_registers = self.feature_manager.get_register_lengths()

            self.config_entry.runtime_data.client.set_register_profile(
                firmware_version=self.feature_manager.firmware_version,
                modbus_map_version=self.feature_manager.modbus_map_version,
                input_register_length=self.input_registers,
                holding_register_length=self.holding_registers,
            )

            LOGGER.debug("Coordinator setup complete for %s", self.config_entry.entry_id)
        except ValueError as exception:
            LOGGER.error("Device validation failed: %s", exception)
            raise ConfigEntryNotReady(str(exception)) from exception

    async def _async_update_data(self) -> Any:
        """
        Fetch data from API endpoint.

        This is the only method that should be implemented in a DataUpdateCoordinator.
        It is called automatically based on the update_interval.

        Context-based fetching:
        The coordinator tracks which entities are currently listening via async_contexts().
        This allows optimizing API calls to only fetch data that's actually needed.
        For example, if only sensor entities are enabled, we can skip fetching switch data.

        The API client uses the credentials from config_entry to authenticate:
        - username: from config_entry.data["username"]
        - password: from config_entry.data["password"]

        Expected API response structure (example):
        {
            "userId": 1,      # Used as device identifier
            "id": 1,          # Data record ID
            "title": "...",   # Additional metadata
            "body": "...",    # Additional content
            # In production, would include:
            # "air_quality": {"aqi": 45, "pm25": 12.3},
            # "filter": {"life_remaining": 75, "runtime_hours": 324},
            # "settings": {"fan_speed": "medium", "humidity": 55}
        }

        Returns:
            The data from the API as a dictionary.

        Raises:
            ConfigEntryAuthFailed: If authentication fails, triggers reauthentication.
            UpdateFailed: If data fetching fails for other reasons, optionally with retry_after.
        """
        try:
            raw_data = await self.config_entry.runtime_data.client.async_get_data()
            processed_data = to_coordinator_payload(parse_device_data(raw_data))
        except AirfiApiClientAuthenticationError as exception:
            LOGGER.warning("Authentication error - %s", exception)
            raise ConfigEntryAuthFailed(
                translation_domain="airfi",
                translation_key="authentication_failed",
            ) from exception
        except AirfiApiClientError as exception:
            LOGGER.exception("Error communicating with API")
            # If the API provides rate limit information, you can honor it:
            # if hasattr(exception, 'retry_after'):
            #     raise UpdateFailed(retry_after=exception.retry_after) from exception
            raise UpdateFailed(
                translation_domain="airfi",
                translation_key="update_failed",
            ) from exception
        else:
            return processed_data

    async def async_set_holding_register(self, address: int, value: int) -> None:
        """Write a holding register value via the API client.

        This is the coordinator write bridge — entities call this method
        instead of the API client directly to maintain the three-layer
        architecture.

        Args:
            address: 1-based Modbus holding register address (e.g. 1 for 4x00001).
            value: Integer value to write.

        Raises:
            AirfiApiClientError: Re-raised after logging if the write fails.
        """
        try:
            await self.config_entry.runtime_data.client.async_write_holding_register(address, value)
        except AirfiApiClientError as exception:
            LOGGER.warning("Failed to write holding register %d: %s", address, exception)
            raise
