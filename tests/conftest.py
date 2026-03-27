"""Shared fixtures for Airfi tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airfi.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry for Airfi."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_SERIAL_NUMBER: "AIRFI-12345",
        },
        unique_id="airfi-12345",
        title="Airfi AIRFI-12345",
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations) -> None:
    """Enable custom integration loading in tests."""
    del enable_custom_integrations


@pytest.fixture
def mock_integration() -> MagicMock:
    """Create a mock integration object for runtime data."""
    return MagicMock()
