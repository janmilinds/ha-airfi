"""Repairs platform for Airfi."""

from typing import TYPE_CHECKING

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .config_flow_handler.schemas import get_address_schema, get_confirm_schema, get_modbus_id_schema
from .config_flow_handler.validators import AddressIdentity, check_address_identity, connection_error
from .const import CONF_MODBUS_ID, CONF_SERIAL_NUMBER, ISSUE_DEVICE_UNREACHABLE
from .utils.error_mapping import ERROR_NO_RESPONSE

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
    """Repair flow for the address, or the Modbus ID, of a unit that no longer answers."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry
        self._host: str = entry.data.get(CONF_HOST, "")
        self._identity = AddressIdentity.UNHEARD
        self._modbus_id: int = entry.data[CONF_MODBUS_ID]

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Ask for the address, and try it with the stored Modbus ID."""
        errors: dict[str, str] = {}

        # Home Assistant opens the flow with {"issue_id": ...} as input, so only a host means a submitted form.
        if user_input is not None and CONF_HOST in user_input:
            self._host = user_input[CONF_HOST]
            self._identity = check_address_identity(self.hass, self._host, self._entry.data[CONF_SERIAL_NUMBER])
            if self._identity is AddressIdentity.OTHER_UNIT:
                errors["base"] = "wrong_device"
            elif (error := await connection_error(self.hass, self._host, self._modbus_id)) is None:
                return await self._async_confirm_or_store()
            elif error == ERROR_NO_RESPONSE:
                return await self.async_step_modbus_id()
            else:
                errors["base"] = error

        return self.async_show_form(
            step_id="init",
            data_schema=get_address_schema(self._host),
            errors=errors,
            description_placeholders={
                "name": self._entry.title,
            },
        )

    async def async_step_modbus_id(self, user_input: dict[str, float] | None = None) -> RepairsFlowResult:
        """Ask for the Modbus ID of a unit that took the connection but did not answer."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._modbus_id = int(user_input[CONF_MODBUS_ID])
            if (error := await connection_error(self.hass, self._host, self._modbus_id)) is None:
                return await self._async_confirm_or_store()
            errors["base"] = error
        return self.async_show_form(
            step_id="modbus_id",
            data_schema=get_modbus_id_schema(self._modbus_id),
            errors=errors,
            description_placeholders={"host": self._host, "name": self._entry.title},
        )

    async def async_step_unverified(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Ask the user to confirm an address no unit was heard announcing itself from."""
        if user_input is not None:
            return self._async_store()
        return self.async_show_form(
            step_id="unverified",
            data_schema=get_confirm_schema(),
            description_placeholders={"host": self._host, "name": self._entry.title},
        )

    async def _async_confirm_or_store(self) -> RepairsFlowResult:
        """Store a unit that answered, after asking when no unit was heard announcing itself from the address."""
        if self._identity is AddressIdentity.UNHEARD:
            return await self.async_step_unverified()
        return self._async_store()

    def _async_store(self) -> RepairsFlowResult:
        """Store the address and Modbus ID, and set the entry up again."""
        changed = self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_HOST: self._host, CONF_MODBUS_ID: self._modbus_id},
        )
        # A loaded entry with changed data already reloads through its update listener.
        if not changed or self._entry.state is not ConfigEntryState.LOADED:
            self.hass.config_entries.async_schedule_reload(self._entry.entry_id)
        return self.async_create_entry(data={})
