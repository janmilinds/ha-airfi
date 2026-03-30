"""
Config flow for Airfi.

This module implements the main configuration flow including:
- Initial user setup
- Reconfiguration of existing entries

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from slugify import slugify

from custom_components.airfi.config_flow_handler.schemas import (
    get_discovery_confirm_schema,
    get_discovery_select_schema,
    get_reconfigure_schema,
    get_user_schema,
)
from custom_components.airfi.config_flow_handler.validators import validate_connection
from custom_components.airfi.const import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_INITIAL_SCAN_TIMEOUT_SECONDS,
    DISCOVERY_SCAN_TIMEOUT_SECONDS,
    DOMAIN,
    LOGGER,
)
from custom_components.airfi.utils.discovery import AirfiDiscoveryService
from custom_components.airfi.utils.error_mapping import map_connection_exception_to_error
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

if TYPE_CHECKING:
    from custom_components.airfi.config_flow_handler.options_flow import AirfiOptionsFlow


class AirfiConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for Airfi.

    This class manages the configuration flow for the integration, including
    initial setup and reconfiguration.

    Supported flows:
    - user: Initial setup via UI
    - reconfigure: Update existing configuration

    For more details:
    https://developers.home-assistant.io/docs/config_entries_config_flow_handler
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow handler."""
        super().__init__()
        self.discovered_devices: list = []
        self.selected_device: Any | None = None
        self.discovery_task: asyncio.Task[list] | None = None
        self._discovery_accumulate: bool = False

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AirfiOptionsFlow:
        """
        Get the options flow for this handler.

        Returns:
            The options flow instance for modifying integration options.

        """
        from custom_components.airfi.config_flow_handler.options_flow import AirfiOptionsFlow  # noqa: PLC0415

        return AirfiOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle a flow initialized by the user.

        This entry point starts automatic discovery immediately and only shows
        manual setup options if discovery does not find any devices.

        Args:
            user_input: Direct manual input for backwards compatibility.

        Returns:
            The config flow result showing discovery progress or the next step.

        """
        if user_input is not None:
            return await self.async_step_manual(user_input)

        if self.discovery_task is None:
            self.discovery_task = self.hass.async_create_task(self._async_run_discovery())

        if self.discovery_task.done():
            if (exception := self.discovery_task.exception()) is not None:
                LOGGER.error("Discovery scan failed: %s", exception)
                return self.async_show_progress_done(next_step_id="fallback")

            if self.discovered_devices:
                return self.async_show_progress_done(next_step_id="discovery_select")

            return self.async_show_progress_done(next_step_id="fallback")

        return self.async_show_progress(
            step_id="user",
            progress_action="discovering_devices",
            progress_task=self.discovery_task,
        )

    async def _async_run_discovery(self) -> list:
        """Run discovery scan and cache discovered devices for later flow steps."""
        existing_by_key = {d.unique_key: d for d in self.discovered_devices} if self._discovery_accumulate else {}
        self._discovery_accumulate = False
        configured_serials = self._get_configured_serial_numbers()

        discovery_service = AirfiDiscoveryService()

        # Two-stage startup scan:
        # 1) quick 5s scan for fast discovery UX
        # 2) if still empty, run one longer 10s fallback scan automatically
        new_devices = await discovery_service.async_scan(timeout_seconds=DISCOVERY_INITIAL_SCAN_TIMEOUT_SECONDS)
        if not existing_by_key and not new_devices:
            new_devices = await discovery_service.async_scan(timeout_seconds=DISCOVERY_SCAN_TIMEOUT_SECONDS)

        for device in new_devices:
            if str(device.serial) in configured_serials:
                continue
            existing_by_key[device.unique_key] = device

        self.discovered_devices = list(existing_by_key.values())
        return self.discovered_devices

    def _get_configured_serial_numbers(self) -> set[str]:
        """Return serial numbers that are already configured in this integration."""
        serials: set[str] = set()
        for entry in self._async_current_entries():
            serial = entry.data.get(CONF_SERIAL_NUMBER)
            if serial is not None:
                serials.add(str(serial))
        return serials

    async def async_step_fallback(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show fallback options after automatic discovery finds no devices."""
        self.discovery_task = None
        return self.async_show_menu(
            step_id="fallback",
            menu_options=["discovery", "manual"],
        )

    async def async_step_manual(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle manual host and serial number entry.

        Args:
            user_input: The user input from the manual config form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.

        """
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_connection(
                    self.hass,
                    host=user_input[CONF_HOST],
                )
            except Exception as exception:  # noqa: BLE001
                errors["base"] = self._map_exception_to_error(exception)
            else:
                serial = user_input[CONF_SERIAL_NUMBER]
                await self.async_set_unique_id(slugify(str(serial)))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Airfi {user_input.get(CONF_MODEL_NAME, serial)}",
                    data={
                        **user_input,
                        CONF_MODEL_NAME: user_input.get(CONF_MODEL_NAME, "Airfi"),
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=get_user_schema(user_input),
            errors=errors,
            description_placeholders={
                "documentation_url": "https://github.com/janmilinds/ha-airfi",
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfiguration of the integration.

        Allows users to update the connection settings without removing and re-adding the integration.

        Args:
            user_input: The user input from the reconfigure form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.

        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_connection(
                    self.hass,
                    host=user_input[CONF_HOST],
                )
            except Exception as exception:  # noqa: BLE001
                errors["base"] = self._map_exception_to_error(exception)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(
                host=entry.data.get(CONF_HOST, ""),
                serial_number=entry.data.get(CONF_SERIAL_NUMBER),
            ),
            errors=errors,
        )

    async def async_step_discovery(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle discovery initiated by user or flow.

        Scans for Airfi devices on the network using UDP multicast and presents
        a list to the user for selection.

        Args:
            user_input: Not used for discovery scan.

        Returns:
            The config flow result showing discovered devices or error.

        """
        self.discovery_task = None
        self.discovered_devices = []
        self.selected_device = None
        return await self.async_step_user()

    async def async_step_discovery_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle selection of discovered device.

        Shows a list of discovered devices and allows the user to select one
        to configure.

        Args:
            user_input: User selection from the device list, or None for initial form.

        Returns:
            The config flow result showing the confirmation step or error.

        """
        if user_input is not None:
            # Find selected device by unique_key
            selected_key = user_input.get("device")

            if selected_key == "__scan_more__":
                self._discovery_accumulate = True
                self.discovery_task = None
                return await self.async_step_user()

            if selected_key == "__manual__":
                return await self.async_step_manual()

            for device in self.discovered_devices:
                if device.unique_key == selected_key:
                    self.selected_device = device
                    return await self.async_step_discovery_confirm()

            return self.async_abort(reason="invalid_selection")

        return self.async_show_form(
            step_id="discovery_select",
            data_schema=get_discovery_select_schema(self.discovered_devices),
            description_placeholders={
                "count": str(len(self.discovered_devices)),
            },
        )

    async def async_step_discovery_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle confirmation and naming of discovered device.

        Shows device details (host, serial) and allows user to set a custom name
        before creating the config entry.

        Args:
            user_input: Confirmed data with optional custom name.

        Returns:
            The config flow result (entry creation or next device, or abort).

        """
        if self.selected_device is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            # Validate connection to discovered host
            errors: dict[str, str] = {}
            try:
                await validate_connection(
                    self.hass,
                    host=self.selected_device.host,
                )
            except Exception as exception:  # noqa: BLE001
                errors["base"] = self._map_exception_to_error(exception)
                return self.async_show_form(
                    step_id="discovery_confirm",
                    data_schema=get_discovery_confirm_schema(
                        self.selected_device,
                        suggested_name=user_input.get("name", ""),
                    ),
                    errors=errors,
                )
            else:
                # Set unique_id to prevent duplicates
                await self.async_set_unique_id(slugify(str(self.selected_device.serial)))
                self._abort_if_unique_id_configured()

                # Create entry with user-provided name
                entry_result = self.async_create_entry(
                    title=user_input.get("name") or f"Airfi {self.selected_device.model_name}",
                    data={
                        CONF_HOST: self.selected_device.host,
                        CONF_SERIAL_NUMBER: self.selected_device.serial,
                        CONF_MODEL_NAME: self.selected_device.model_name,
                    },
                )

                # If more devices remain, cascade to next
                if len(self.discovered_devices) > 1:
                    self.discovered_devices.remove(self.selected_device)
                    self.selected_device = None
                    return await self.async_step_discovery_select()

                return entry_result

        # Show confirmation form
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=get_discovery_confirm_schema(self.selected_device),
            description_placeholders={
                "host": self.selected_device.host,
                "serial": str(self.selected_device.serial),
                "model": self.selected_device.model_name,
            },
        )

    def _map_exception_to_error(self, exception: Exception) -> str:
        """
        Map API exceptions to user-facing error keys.

        Args:
            exception: The exception that was raised.

        Returns:
            The error key for display in the config flow form.

        """
        LOGGER.warning("Error in config flow: %s", exception)
        return map_connection_exception_to_error(exception)


__all__ = ["AirfiConfigFlowHandler"]
