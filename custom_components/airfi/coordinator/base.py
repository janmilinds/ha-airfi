"""
Core DataUpdateCoordinator implementation for Airfi.

This module contains the main coordinator class that manages data fetching
and updates for all entities in the integration. It handles refresh cycles,
error handling, and triggers rediscovery when needed.

Recovery state machine:
    IDLE        — device is reachable, normal polling
    RECOVERING  — device unreachable for > RECOVERY_TRIGGER_SECONDS,
                  rediscovery active; repairs issue raised after
                  RECOVERY_ISSUE_SECONDS
    (back to IDLE when connection is restored, issue auto-resolved)

For more information on coordinators:
https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any

from custom_components.airfi.api import AirfiApiClientError
from custom_components.airfi.const import (
    CONF_SERIAL_NUMBER,
    DISCOVERY_RECOVERY_COOLDOWN_SECONDS,
    DISCOVERY_RECOVERY_SCAN_TIMEOUT_SECONDS,
    DOMAIN,
    ISSUE_DEVICE_UNREACHABLE,
    LOGGER,
    RECOVERY_ISSUE_SECONDS,
    RECOVERY_TRIGGER_SECONDS,
)
from custom_components.airfi.coordinator.data_processing import parse_device_data, to_coordinator_payload
from custom_components.airfi.coordinator.error_handling import (
    log_connection_failure,
    log_modbus_failure,
    should_try_rediscovery,
)
from custom_components.airfi.coordinator.feature_manager import AirfiFeatureManager
from custom_components.airfi.utils.discovery import AirfiDiscoveryService
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from custom_components.airfi.data import AirfiConfigEntry


class RecoveryState(Enum):
    """Recovery state of the coordinator."""

    IDLE = "idle"
    RECOVERING = "recovering"


class AirfiDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching data from the Airfi device.

    This coordinator handles all data fetching for the integration and distributes
    updates to all entities. It manages:
    - Periodic Modbus polling based on update_interval
    - Communication error handling and IP recovery via rediscovery
    - Repairs issue lifecycle when the device is unreachable for an extended period
    - Data distribution to all entities

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
        self.hw_version: str = ""
        self._last_rediscovery_attempt: float | None = None
        self._connection_lost_at: float | None = None
        self._recovery_state: RecoveryState = RecoveryState.IDLE
        self._issue_raised: bool = False

    @property
    def _device_unreachable_issue_id(self) -> str:
        """Return the issue ID for unreachable-device repairs for this entry."""
        return f"{ISSUE_DEVICE_UNREACHABLE}_{self.config_entry.entry_id}"

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
        device_name = f"Airfi {self.config_entry.data.get(CONF_SERIAL_NUMBER, 'Unknown')}"
        try:
            lookup_registers = await self.config_entry.runtime_data.client.async_get_lookup_registers()
        except AirfiApiClientError as exception:
            if should_try_rediscovery(exception) and await self._async_try_recover_host(force=True):
                try:
                    lookup_registers = await self.config_entry.runtime_data.client.async_get_lookup_registers()
                except AirfiApiClientError as retry_exception:
                    raise ConfigEntryNotReady(str(retry_exception)) from retry_exception
            else:
                raise ConfigEntryNotReady(str(exception)) from exception
        try:
            # Initialize feature manager and validate firmware
            self.feature_manager.initialize(device_name, lookup_registers)

            # Cache hw_version for device info
            self.hw_version = self.feature_manager.hw_version

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
        Fetch data from Airfi device via Modbus.

        This is the only method that should be implemented in a DataUpdateCoordinator.
        It is called automatically based on the update_interval.

        Returns:
        Coordinator payload dict with parsed register data.

        Raises:
        UpdateFailed: If Modbus communication fails after recovery attempts.
        """
        try:
            raw_data = await self.config_entry.runtime_data.client.async_get_data()
            self._async_on_connection_restored()
            return to_coordinator_payload(parse_device_data(raw_data))
        except AirfiApiClientError as exception:
            if should_try_rediscovery(exception):
                self._async_on_connection_lost()
                if await self._async_try_recover_host():
                    try:
                        raw_data = await self.config_entry.runtime_data.client.async_get_data()
                        self._async_on_connection_restored()
                        return to_coordinator_payload(parse_device_data(raw_data))
                    except AirfiApiClientError as retry_exception:
                        if should_try_rediscovery(retry_exception):
                            log_connection_failure(retry_exception, "post-rediscovery fetch")
                        else:
                            log_modbus_failure(retry_exception, "post-rediscovery fetch")
                        raise UpdateFailed(
                            translation_domain="airfi",
                            translation_key="update_failed_rediscovery",
                        ) from retry_exception

            if should_try_rediscovery(exception):
                log_connection_failure(exception, "data fetch")
            else:
                log_modbus_failure(exception, "data fetch")
            raise UpdateFailed(
                translation_domain="airfi",
                translation_key="update_failed",
            ) from exception

    def _async_on_connection_lost(self) -> None:
        """Handle a connection loss event and trigger recovery if thresholds are met."""
        loop = asyncio.get_running_loop()
        now = loop.time()

        if self._connection_lost_at is None:
            self._connection_lost_at = now
            LOGGER.debug("Device connection lost, starting outage timer")

        outage_duration = now - self._connection_lost_at

        if outage_duration >= RECOVERY_TRIGGER_SECONDS and self._recovery_state == RecoveryState.IDLE:
            self._recovery_state = RecoveryState.RECOVERING
            LOGGER.warning(
                "Device unreachable for %.0f seconds, activating rediscovery",
                outage_duration,
            )

        if outage_duration >= RECOVERY_ISSUE_SECONDS and not self._issue_raised:
            self._issue_raised = True
            LOGGER.warning(
                "Device unreachable for %.0f minutes, raising repair issue",
                outage_duration / 60,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._device_unreachable_issue_id,
                data={
                    "entry_id": self.config_entry.entry_id,
                },
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_DEVICE_UNREACHABLE,
                translation_placeholders={
                    "name": self.config_entry.title,
                },
            )

    def _async_on_connection_restored(self) -> None:
        """Handle a successful connection and reset recovery state."""
        if self._connection_lost_at is None and self._recovery_state == RecoveryState.IDLE and not self._issue_raised:
            return

        LOGGER.info("Device connection restored, resetting recovery state")
        self._connection_lost_at = None
        self._recovery_state = RecoveryState.IDLE

        if self._issue_raised:
            self._issue_raised = False
            ir.async_delete_issue(self.hass, DOMAIN, self._device_unreachable_issue_id)

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

    async def _async_try_recover_host(self, *, force: bool = False) -> bool:
        """Try to rediscover the configured serial number at a new IP address.

        Only runs when in RECOVERING state and the cooldown has elapsed,
        unless explicitly forced (used during initial setup).
        """
        if not force and self._recovery_state != RecoveryState.RECOVERING:
            return False

        serial = self.config_entry.data.get(CONF_SERIAL_NUMBER)
        if serial is None:
            return False

        loop = asyncio.get_running_loop()
        now = loop.time()
        if (
            self._last_rediscovery_attempt is not None
            and now - self._last_rediscovery_attempt < DISCOVERY_RECOVERY_COOLDOWN_SECONDS
        ):
            return False

        self._last_rediscovery_attempt = now
        discovery_service = AirfiDiscoveryService()
        discovered_devices = await discovery_service.async_scan(
            timeout_seconds=DISCOVERY_RECOVERY_SCAN_TIMEOUT_SECONDS,
        )

        target_serials = {str(serial)}
        serial_digits = "".join(char for char in str(serial) if char.isdigit())
        if serial_digits:
            target_serials.add(str(int(serial_digits)))

        for device in discovered_devices:
            if str(device.serial) not in target_serials:
                continue

            current_host = self.config_entry.data.get(CONF_HOST)
            if device.host == current_host:
                return False

            LOGGER.warning(
                "Recovered Airfi device %s at new IP %s (was %s)",
                str(device.serial),
                device.host,
                current_host,
            )
            self.config_entry.runtime_data.client.update_host(device.host)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_HOST: device.host},
            )
            return True

        return False
