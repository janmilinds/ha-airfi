"""
Config flow schemas.

Schemas for the main configuration flow steps:
- User setup
- Reconfiguration, and the address a repair asks for
- The Modbus ID of a unit that does not answer
- Discovery
- Discovery confirm (select device + override name)

When this file grows too large (>300 lines), consider splitting into:
- user.py: User setup schemas
- reconfigure.py: Reconfiguration schemas
- discovery.py: Discovery schemas
"""

from collections.abc import Mapping
from typing import Any

import probatio

from custom_components.airfi_home.const import (
    AIRFI_MODELS,
    CONF_MODBUS_ID,
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_OPTION_MANUAL,
    DISCOVERY_OPTION_SCAN_MORE,
    MODBUS_ID_MAX,
    MODBUS_ID_MIN,
    SECTION_ADVANCED,
)
from custom_components.airfi_home.utils.discovery import AirfiDiscoveredDevice, get_model_name, unit_title
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector


def _get_model_options() -> list[selector.SelectOptionDict]:
    """Return manual model selector options matching autodiscovery names."""
    return [
        selector.SelectOptionDict(value=name, label=name)
        for model_id in range(1, (len(AIRFI_MODELS) * 2) + 1)
        if (name := get_model_name(model_id))
    ]


def get_user_schema(defaults: Mapping[str, Any] | None = None) -> probatio.Schema:
    """
    Get schema for user step (initial setup).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for user connection settings input.

    """
    defaults = defaults or {}
    return probatio.Schema(
        {
            **_host_field(defaults.get(CONF_HOST, probatio.UNDEFINED)),
            probatio.Required(
                CONF_SERIAL_NUMBER,
                default=defaults.get(CONF_SERIAL_NUMBER, probatio.UNDEFINED),
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            probatio.Required(
                CONF_MODEL_NAME,
                default=defaults.get(CONF_MODEL_NAME, probatio.UNDEFINED),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_get_model_options(),
                    sort=False,
                ),
            ),
            probatio.Optional(
                CONF_NAME,
                description={"suggested_value": defaults.get(CONF_NAME)},
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
        },
    )


def _host_field(host: Any) -> dict[probatio.Required, selector.TextSelector]:
    """Return the address field, pre-filled."""
    return {
        probatio.Required(CONF_HOST, default=host): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
    }


def _modbus_id_field(modbus_id: int) -> dict[probatio.Required, selector.NumberSelector]:
    """Return the Modbus ID field, pre-filled."""
    return {
        probatio.Required(CONF_MODBUS_ID, default=modbus_id): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MODBUS_ID_MIN,
                max=MODBUS_ID_MAX,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            ),
        ),
    }


def get_address_schema(host: str) -> probatio.Schema:
    """
    Get schema for a step that asks only for the unit's address.

    Args:
        host: Address to pre-fill in the form.

    Returns:
        Schema with the address field.

    """
    return probatio.Schema(_host_field(host))


def get_reconfigure_schema(host: str, modbus_id: int, *, show_advanced: bool = False) -> probatio.Schema:
    """
    Get schema for reconfigure step: the address, and the Modbus ID in a section that starts collapsed.

    Args:
        host: Address to pre-fill in the form.
        modbus_id: Modbus ID to pre-fill in the form.
        show_advanced: Open the section, such as when the unit did not answer to the ID in it.

    Returns:
        Schema for reconfiguration.

    """
    return probatio.Schema(
        {
            **_host_field(host),
            probatio.Required(SECTION_ADVANCED): section(
                probatio.Schema(_modbus_id_field(modbus_id)),
                {"collapsed": not show_advanced},
            ),
        },
    )


def get_modbus_id_schema(modbus_id: int) -> probatio.Schema:
    """
    Get schema for the step that asks for the Modbus ID of a unit that did not answer.

    Args:
        modbus_id: Modbus ID to pre-fill in the form, normally the one just tried.

    Returns:
        Schema with the Modbus ID field.

    """
    return probatio.Schema(_modbus_id_field(modbus_id))


def get_discovery_select_schema(devices: list[AirfiDiscoveredDevice]) -> probatio.Schema:
    """
    Get schema for discovery device selection step.

    Args:
        devices: List of discovered devices to select from.

    Returns:
        Voluptuous schema for selecting a discovered device.

    """
    device_options = [
        selector.SelectOptionDict(
            value=device.unique_key,
            label=f"{unit_title(device.model_name)} · {device.host} · {device.serial}",
        )
        for device in devices
    ]
    device_options.extend(
        selector.SelectOptionDict(value=option, label=option)
        for option in (DISCOVERY_OPTION_SCAN_MORE, DISCOVERY_OPTION_MANUAL)
    )

    return probatio.Schema(
        {
            probatio.Required("device"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=device_options,
                    translation_key="discovered_device",
                ),
            ),
        },
    )


def get_discovery_confirm_schema(
    device: AirfiDiscoveredDevice,
    suggested_name: str | None = None,
) -> probatio.Schema:
    """
    Get schema for discovery device confirmation and naming.

    Host and serial are shown via description placeholders (not editable).
    Only the device name is editable and optional.

    Args:
        device: Discovered device to confirm.
        suggested_name: Optional suggested name for the device.

    Returns:
        Voluptuous schema for confirming device and setting custom name.

    """
    default_name = suggested_name or unit_title(device.model_name)

    return probatio.Schema(
        {
            probatio.Optional(CONF_NAME, default=default_name): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
            ),
        },
    )


def get_confirm_schema() -> probatio.Schema:
    """
    Get schema for a step that only asks the user to confirm.

    Returns:
        An empty schema; the step's description says what is confirmed.

    """
    return probatio.Schema({})


__all__ = [
    "get_address_schema",
    "get_confirm_schema",
    "get_discovery_confirm_schema",
    "get_discovery_select_schema",
    "get_modbus_id_schema",
    "get_reconfigure_schema",
    "get_user_schema",
]
