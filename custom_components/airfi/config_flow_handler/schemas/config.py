"""
Config flow schemas.

Schemas for the main configuration flow steps:
- User setup
- Reconfiguration
- Reauthentication
- Discovery
- Discovery confirm (select device + override name)

When this file grows too large (>300 lines), consider splitting into:
- user.py: User setup schemas
- reauth.py: Reauthentication schemas
- reconfigure.py: Reconfiguration schemas
- discovery.py: Discovery schemas
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from custom_components.airfi.const import AIRFI_MODELS, CONF_MODEL_NAME, CONF_SERIAL_NUMBER
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice, get_model_name
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector


def _get_model_options() -> list[selector.SelectOptionDict]:
    """Return manual model selector options matching autodiscovery names."""
    return [
        selector.SelectOptionDict(
            value=get_model_name(model_id),
            label=get_model_name(model_id),
        )
        for model_id in range(1, (len(AIRFI_MODELS) * 2) + 1)
    ]


def get_user_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for user step (initial setup).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for user credentials input.

    """
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=defaults.get(CONF_HOST, vol.UNDEFINED),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Required(
                CONF_SERIAL_NUMBER,
                default=defaults.get(CONF_SERIAL_NUMBER, vol.UNDEFINED),
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            vol.Required(
                CONF_MODEL_NAME,
                default=defaults.get(CONF_MODEL_NAME, vol.UNDEFINED),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_get_model_options(),
                    sort=False,
                ),
            ),
        },
    )


def get_reconfigure_schema(host: str, serial_number: str | None) -> vol.Schema:
    """
    Get schema for reconfigure step.

    Args:
        host: Current host to pre-fill in the form.
        serial_number: Unused; kept for call-site compatibility.

    Returns:
        Voluptuous schema for reconfiguration.

    """
    del serial_number
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=host,
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
        },
    )


def get_reauth_schema(host: str, serial_number: str | None) -> vol.Schema:
    """
    Get schema for reauthentication step.

    Args:
        username: Current username to pre-fill in the form.

    Returns:
        Voluptuous schema for reauthentication.

    """
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                default=host,
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Required(
                CONF_SERIAL_NUMBER,
                default=serial_number if serial_number is not None else vol.UNDEFINED,
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
        },
    )


def get_discovery_select_schema(devices: list[AirfiDiscoveredDevice]) -> vol.Schema:
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
            label=f"Airfi {device.model_name} ({device.host}) - S/N: {device.serial}",
        )
        for device in devices
    ]
    device_options.append(
        selector.SelectOptionDict(
            value="__scan_more__",
            label="Search more...",
        )
    )
    device_options.append(
        selector.SelectOptionDict(
            value="__manual__",
            label="Add device manually...",
        )
    )

    return vol.Schema(
        {
            vol.Required("device"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=device_options,
                ),
            ),
        },
    )


def get_discovery_confirm_schema(
    device: AirfiDiscoveredDevice,
    suggested_name: str | None = None,
) -> vol.Schema:
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
    default_name = suggested_name or f"Airfi {device.model_name}"

    return vol.Schema(
        {
            vol.Optional("name", default=default_name): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
            ),
        },
    )


__all__ = [
    "get_discovery_confirm_schema",
    "get_discovery_select_schema",
    "get_reauth_schema",
    "get_reconfigure_schema",
    "get_user_schema",
]
