"""
API package for Airfi.

Architecture:
    Three-layer data flow: Entities → Coordinator → API Client.
    Only the coordinator should call the API client. Entities must never
    import or call the API client directly.

Exception hierarchy:
    AirfiApiClientError (base)
    ├── AirfiApiClientConnectionError (TCP unreachable / timeout)
    └── AirfiApiClientModbusError (Modbus protocol failure)

Coordinator exception mapping:
    AirfiApiClientConnectionError → may trigger rediscovery → UpdateFailed
    AirfiApiClientModbusError     → UpdateFailed (no rediscovery)
    AirfiApiClientError           → UpdateFailed
"""

from .client import AirfiApiClient, AirfiApiClientConnectionError, AirfiApiClientError, AirfiApiClientModbusError

__all__ = [
    "AirfiApiClient",
    "AirfiApiClientConnectionError",
    "AirfiApiClientError",
    "AirfiApiClientModbusError",
]
