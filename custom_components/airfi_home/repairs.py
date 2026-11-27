"""Repairs platform for Airfi."""

from typing import TYPE_CHECKING

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .config_flow_handler.schemas import get_confirm_schema, get_reconfigure_schema
from .config_flow_handler.validators import AddressIdentity, check_address_identity, validate_connection
from .const import CONF_SERIAL_NUMBER, ISSUE_DEVICE_UNREACHABLE
from .utils.error_mapping import map_connection_exception_to_error

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
        self._unverified_host: str | None = None

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Handle the initial repair step."""
        errors: dict[str, str] = {}

        # Home Assistant opens the flow with {"issue_id": ...} as input, so only a host means a submitted form.
        if user_input is not None and CONF_HOST in user_input:
            host = user_input[CONF_HOST]
            try:
                await validate_connection(
                    self.hass,
                    host=host,
                )
            except Exception as exception:  # noqa: BLE001
                errors["base"] = self._map_exception_to_error(exception)
            else:
                identity = check_address_identity(self.hass, host, self._entry.data[CONF_SERIAL_NUMBER])
                if identity is AddressIdentity.OTHER_UNIT:
                    errors["base"] = "wrong_device"
                elif identity is AddressIdentity.UNHEARD:
                    self._unverified_host = host
                    return await self.async_step_unverified()
                else:
                    return self._async_store_host(host)

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

    async def async_step_unverified(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Ask the user to confirm an address no unit was heard announcing itself from."""
        if TYPE_CHECKING:
            assert self._unverified_host is not None
        if user_input is not None:
            return self._async_store_host(self._unverified_host)
        return self.async_show_form(
            step_id="unverified",
            data_schema=get_confirm_schema(),
            description_placeholders={"host": self._unverified_host, "name": self._entry.title},
        )

    def _async_store_host(self, host: str) -> RepairsFlowResult:
        """Store the new address and set the entry up again."""
        changed = self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_HOST: host},
        )
        # A loaded entry with changed data already reloads through its update listener.
        if not changed or self._entry.state is not ConfigEntryState.LOADED:
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
        return self.async_create_entry(data={})

    @staticmethod
    def _map_exception_to_error(exception: Exception) -> str:
        """Map connection validation exceptions to form error keys."""
        return map_connection_exception_to_error(exception)
