"""
API package for Airfi.

Architecture:
    Three-layer data flow: Entities → Coordinator → API Client.
    Only the coordinator should call the API client. Entities must never
    import or call the API client directly.

Exception hierarchy:
    AirfiApiClientError (base)
    └── AirfiApiClientCommunicationError (network/timeout)

Coordinator exception mapping:
    ApiClientCommunicationError → UpdateFailed (auto-retry)
    ApiClientError             → UpdateFailed (auto-retry)
"""

from .client import AirfiApiClient, AirfiApiClientCommunicationError, AirfiApiClientError

__all__ = [
    "AirfiApiClient",
    "AirfiApiClientCommunicationError",
    "AirfiApiClientError",
]
