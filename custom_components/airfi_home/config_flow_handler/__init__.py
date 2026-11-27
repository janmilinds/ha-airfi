"""
Config flow handler package for Airfi.

This package implements the configuration flows for the integration, organized
for maintainability and scalability.

Package structure:
------------------
- config_flow.py: Main configuration flow (user setup, reconfigure)
- schemas/: Voluptuous schemas for all forms (user, reconfigure, discovery)
- validators/: Validation logic for user inputs and connection settings

Usage:
------
The main config flow handler is imported in config_flow.py at the integration root:

    from .config_flow_handler import AirfiConfigFlowHandler

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from .config_flow import AirfiConfigFlowHandler

__all__ = [
    "AirfiConfigFlowHandler",
]
