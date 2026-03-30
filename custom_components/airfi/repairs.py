"""Repairs platform for Airfi."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.airfi.config_flow_handler.schemas import get_reconfigure_schema
from custom_components.airfi.config_flow_handler.validators import validate_connection
from custom_components.airfi.const import CONF_SERIAL_NUMBER, DOMAIN, ISSUE_DEVICE_UNREACHABLE
from custom_components.airfi.utils.error_mapping import map_connection_exception_to_error
from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    _data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow based on the issue_id."""
    if issue_id.startswith(f"{ISSUE_DEVICE_UNREACHABLE}_"):
        entry_id = issue_id.removeprefix(f"{ISSUE_DEVICE_UNREACHABLE}_")
        if entry := hass.config_entries.async_get_entry(entry_id):
            return DeviceUnreachableRepairFlow(entry)

        raise ValueError(f"Unknown config entry in issue ID: {issue_id}")

    raise ValueError(f"Unknown issue ID: {issue_id}")


class DeviceUnreachableRepairFlow(RepairsFlow):
    """Repair flow for updating the IP address of an unreachable device."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial repair step."""
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
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={**self._entry.data, CONF_HOST: user_input[CONF_HOST]},
                )
                ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            data_schema=get_reconfigure_schema(
                host=self._entry.data.get(CONF_HOST, ""),
                serial_number=self._entry.data.get(CONF_SERIAL_NUMBER),
            ),
            errors=errors,
            description_placeholders={
                "name": self._entry.title,
            },
        )

    @staticmethod
    def _map_exception_to_error(exception: Exception) -> str:
        """Map connection validation exceptions to form error keys."""
        return map_connection_exception_to_error(exception)
