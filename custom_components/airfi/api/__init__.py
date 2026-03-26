"""
API package for airfi.

Architecture:
    Three-layer data flow: Entities → Coordinator → API Client.
    Only the coordinator should call the API client. Entities must never
    import or call the API client directly.

Exception hierarchy:
    AirfiApiClientError (base)
    ├── AirfiApiClientCommunicationError (network/timeout)
    └── AirfiApiClientAuthenticationError (401/403)

Coordinator exception mapping:
    ApiClientAuthenticationError → ConfigEntryAuthFailed (triggers reauth)
    ApiClientCommunicationError → UpdateFailed (auto-retry)
    ApiClientError             → UpdateFailed (auto-retry)
"""

from .client import (
    AirfiApiClient,
    AirfiApiClientAuthenticationError,
    AirfiApiClientCommunicationError,
    AirfiApiClientError,
)

__all__ = [
    "AirfiApiClient",
    "AirfiApiClientAuthenticationError",
    "AirfiApiClientCommunicationError",
    "AirfiApiClientError",
]
