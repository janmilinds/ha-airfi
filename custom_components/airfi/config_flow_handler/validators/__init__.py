"""
Validators for config flow inputs.

This package contains validation functions for user inputs across all flow types.
Validation logic is organized into separate modules for better maintainability
as the integration grows.

Package structure:
-----------------
- connection.py: Connection validators (e.g., testing API connectivity)

When validators grow (>300 lines per file), split further:
 - connection/modbus.py, connection/discovery.py

All validators are re-exported from this __init__.py for convenient imports.
"""

from __future__ import annotations

from custom_components.airfi.config_flow_handler.validators.connection import validate_connection

# Re-export all validators for convenient imports
__all__ = [
    "validate_connection",
]
