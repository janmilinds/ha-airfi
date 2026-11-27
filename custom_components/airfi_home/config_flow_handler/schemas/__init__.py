"""
Data schemas for config flow forms.

This package contains all voluptuous schemas used in config flows.
Schemas are organized into separate modules for better
maintainability as the integration grows.

Package structure:
-----------------
- config.py: Main config flow schemas (user, reconfigure)

When schemas grow (>300 lines per file), split further:
- config/user.py, config/reconfigure.py

All schemas are re-exported from this __init__.py for convenient imports.
"""

from custom_components.airfi_home.config_flow_handler.schemas.config import (
    get_confirm_schema,
    get_discovery_confirm_schema,
    get_discovery_select_schema,
    get_reconfigure_schema,
    get_user_schema,
)

# Re-export all schemas for convenient imports
__all__ = [
    "get_confirm_schema",
    "get_discovery_confirm_schema",
    "get_discovery_select_schema",
    "get_reconfigure_schema",
    "get_user_schema",
]
