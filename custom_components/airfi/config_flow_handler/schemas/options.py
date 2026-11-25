"""
Options flow schemas.

Schemas for the options flow that allows users to modify settings
after initial configuration.

When adding many options, consider grouping them:
- basic_options.py: Common settings (update interval, debug mode)
- advanced_options.py: Advanced settings
- device_options.py: Device-specific settings
"""

from collections.abc import Mapping
from typing import Any

import probatio

from custom_components.airfi.const import DEFAULT_POLL_INTERVAL_SECONDS
from homeassistant.helpers import selector


def get_options_schema(defaults: Mapping[str, Any] | None = None) -> probatio.Schema:
    """
    Get schema for options flow.

    Args:
        defaults: Optional dictionary of current option values.

    Returns:
        Voluptuous schema for options configuration.

    """
    defaults = defaults or {}
    return probatio.Schema(
        {
            probatio.Optional(
                "update_interval_seconds",
                default=defaults.get("update_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=60,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
        },
    )


__all__ = [
    "get_options_schema",
]
