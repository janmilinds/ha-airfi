"""
Config flow for Airfi.

This module implements the main configuration flow including:
- Initial user setup, searching the network first
- Units found by the discovery listener or by Home Assistant's DHCP watcher
- Reconfiguration of existing entries

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

import asyncio
from typing import TYPE_CHECKING, Any

from custom_components.airfi.config_flow_handler.schemas import (
    get_confirm_schema,
    get_discovery_confirm_schema,
    get_discovery_select_schema,
    get_reconfigure_schema,
    get_user_schema,
)
from custom_components.airfi.config_flow_handler.validators import (
    AddressIdentity,
    check_address_identity,
    validate_connection,
)
from custom_components.airfi.const import (
    AIRFI_MAC_PREFIX,
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_INITIAL_SCAN_TIMEOUT_SECONDS,
    DISCOVERY_OPTION_MANUAL,
    DISCOVERY_OPTION_SCAN_MORE,
    DISCOVERY_SCAN_TIMEOUT_SECONDS,
    DOMAIN,
    LOGGER,
)
from custom_components.airfi.utils import normalized_serial
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice, AirfiDiscoveryService, announced_device_at
from custom_components.airfi.utils.error_mapping import map_connection_exception_to_error
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo


class AirfiConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for Airfi.

    This class manages the configuration flow for the integration, including
    initial setup and reconfiguration.

    Supported flows:
    - user: Initial setup via UI, searching the network first
    - integration_discovery: A unit the discovery listener heard
    - dhcp: A unit Home Assistant saw on the network by its MAC address
    - reconfigure: Update existing configuration

    For more details:
    https://developers.home-assistant.io/docs/config_entries_config_flow_handler
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow handler."""
        super().__init__()
        self.discovered_devices: list[AirfiDiscoveredDevice] = []
        self.selected_device: AirfiDiscoveredDevice | None = None
        self.discovery_task: asyncio.Task[list[AirfiDiscoveredDevice]] | None = None
        self._discovery_accumulate: bool = False
        self._unverified_host: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle a flow initialized by the user.

        This entry point starts automatic discovery immediately and only shows
        manual setup options if discovery does not find any devices.

        Args:
            user_input: Unused; the step shows scan progress and has no form.

        Returns:
            The config flow result showing discovery progress or the next step.

        """
        if self.discovery_task is None:
            self.discovery_task = self.hass.async_create_task(self._async_run_discovery())

        if self.discovery_task.done():
            if (exception := self.discovery_task.exception()) is not None:
                if isinstance(exception, OSError):
                    LOGGER.debug(
                        "Discovery scan failed due to a local socket or bind issue: %s; showing fallback error step",
                        exception,
                    )
                else:
                    LOGGER.error("Discovery scan failed", exc_info=exception)
                next_step = "fallback_error" if isinstance(exception, OSError) else "fallback"
                return self.async_show_progress_done(next_step_id=next_step)

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
            menu_options=["scan", "manual"],
        )

    async def async_step_fallback_error(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show fallback options when discovery failed due to a socket error."""
        self.discovery_task = None
        return self.async_show_menu(
            step_id="fallback_error",
            menu_options=["scan", "manual"],
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
            if (serial := normalized_serial(user_input[CONF_SERIAL_NUMBER])) is None:
                errors[CONF_SERIAL_NUMBER] = "invalid_serial"
            elif error := await self._async_connection_error(user_input[CONF_HOST]):
                errors["base"] = error
            elif check_address_identity(self.hass, user_input[CONF_HOST], serial) is AddressIdentity.OTHER_UNIT:
                errors["base"] = "serial_mismatch"
            else:
                return await self._async_create_unit_entry(
                    user_input[CONF_HOST], serial, user_input[CONF_MODEL_NAME], user_input.get(CONF_NAME)
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
            host = user_input[CONF_HOST]
            try:
                await validate_connection(
                    self.hass,
                    host=host,
                )
            except Exception as exception:  # noqa: BLE001
                errors["base"] = self._map_exception_to_error(exception)
            else:
                identity = check_address_identity(self.hass, host, entry.data[CONF_SERIAL_NUMBER])
                if identity is AddressIdentity.OTHER_UNIT:
                    errors["base"] = "wrong_device"
                elif identity is AddressIdentity.UNHEARD:
                    self._unverified_host = host
                    return await self.async_step_reconfigure_unverified()
                else:
                    return self._async_store_reconfigured_host(host)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(
                host=entry.data.get(CONF_HOST, ""),
                serial_number=entry.data.get(CONF_SERIAL_NUMBER),
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_reconfigure_unverified(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Ask the user to confirm an address no unit was heard announcing itself from."""
        if TYPE_CHECKING:
            assert self._unverified_host is not None
        if user_input is not None:
            return self._async_store_reconfigured_host(self._unverified_host)
        return self.async_show_form(
            step_id="reconfigure_unverified",
            data_schema=get_confirm_schema(),
            description_placeholders={"host": self._unverified_host, "name": self._get_reconfigure_entry().title},
        )

    def _async_store_reconfigured_host(self, host: str) -> config_entries.ConfigFlowResult:
        """Store the new address; a loaded entry reloads through its update listener."""
        entry = self._get_reconfigure_entry()
        data = {**entry.data, CONF_HOST: host}
        if entry.state is config_entries.ConfigEntryState.LOADED:
            return self.async_update_and_abort(entry, data=data)
        return self.async_update_reload_and_abort(entry, data=data)

    async def async_step_integration_discovery(
        self,
        discovery_info: AirfiDiscoveredDevice,
    ) -> config_entries.ConfigFlowResult:
        """Store the new address of a unit already set up, or ask the user to add the unit."""
        await self.async_set_unique_id(discovery_info.unique_key)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host}, reload_on_update=False)
        self.selected_device = discovery_info
        self.context["title_placeholders"] = {"name": f"Airfi {discovery_info.model_name}"}
        return await self.async_step_discovery_confirm()

    async def async_step_dhcp(
        self,
        discovery_info: DhcpServiceInfo,
    ) -> config_entries.ConfigFlowResult:
        """
        Offer a unit Home Assistant saw on the network by its MAC address.

        The manifest's matcher can only compare the first six hex digits, which other vendors share, so the seventh is
        checked here, and the unit must announce itself from that address to give its serial number and model.
        """
        if not discovery_info.macaddress.lower().startswith(AIRFI_MAC_PREFIX):
            return self.async_abort(reason="not_airfi_device")
        self._async_abort_entries_match({CONF_HOST: discovery_info.ip})
        if (device := await self._async_find_announcement(discovery_info.ip)) is None:
            return self.async_abort(reason="not_airfi_device")
        return await self.async_step_integration_discovery(device)

    async def _async_find_announcement(self, host: str) -> AirfiDiscoveredDevice | None:
        """Return the unit announcing itself from this address, from the listener or a short scan."""
        if device := announced_device_at(self.hass, host):
            return device
        try:
            devices = await AirfiDiscoveryService().async_scan(timeout_seconds=DISCOVERY_INITIAL_SCAN_TIMEOUT_SECONDS)
        except OSError as err:
            LOGGER.debug("Could not scan for the unit at %s: %s", host, err)
            return None
        return next((device for device in devices if device.host == host), None)

    async def async_step_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Search the network again after a search that found nothing or failed.

        Args:
            user_input: Unused; the step is a menu choice.

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

            if selected_key == DISCOVERY_OPTION_SCAN_MORE:
                self._discovery_accumulate = True
                self.discovery_task = None
                return await self.async_step_user()

            if selected_key == DISCOVERY_OPTION_MANUAL:
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
            The config flow result (entry creation or abort).

        """
        if self.selected_device is None:
            return self.async_abort(reason="invalid_selection")

        errors: dict[str, str] = {}
        suggested_name: str | None = None
        device = self.selected_device
        if user_input is not None:
            if error := await self._async_connection_error(device.host):
                errors["base"] = error
                suggested_name = user_input.get(CONF_NAME, "")
            else:
                return await self._async_create_unit_entry(
                    device.host, device.unique_key, device.model_name, user_input.get(CONF_NAME)
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=get_discovery_confirm_schema(self.selected_device, suggested_name=suggested_name),
            errors=errors,
            description_placeholders={
                "host": self.selected_device.host,
                "serial": str(self.selected_device.serial),
                "model": self.selected_device.model_name,
            },
        )

    async def _async_connection_error(self, host: str) -> str | None:
        """Return the form error for a unit that does not answer at this address, or None when it does."""
        try:
            await validate_connection(self.hass, host=host)
        except Exception as exception:  # noqa: BLE001
            return self._map_exception_to_error(exception)
        return None

    async def _async_create_unit_entry(
        self, host: str, serial: str, model_name: str, name: str | None
    ) -> config_entries.ConfigFlowResult:
        """Add the unit under its serial number, named by the user or by Airfi and its model."""
        await self.async_set_unique_id(serial, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=name or f"Airfi {model_name}",
            data={CONF_HOST: host, CONF_SERIAL_NUMBER: serial, CONF_MODEL_NAME: model_name},
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
