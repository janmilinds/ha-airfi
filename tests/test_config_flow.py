"""Test the Airfi config flow."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.airfi.api import AirfiApiClientCommunicationError
from custom_components.airfi.config_flow_handler.config_flow import AirfiConfigFlowHandler
from custom_components.airfi.const import CONF_MODEL_NAME, CONF_SERIAL_NUMBER
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.unit
async def test_user_flow_creates_entry(hass) -> None:
    """Test that the user flow creates an entry with host and serial number."""
    handler = AirfiConfigFlowHandler()
    handler.hass = hass
    handler.context = {"source": "user"}
    handler.flow_id = "test-flow"
    handler.async_set_unique_id = AsyncMock()

    with (
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(AirfiConfigFlowHandler, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await handler.async_step_user(
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "AIRFI-12345",
                CONF_MODEL_NAME: "Model 60 L",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airfi Model 60 L"
    assert result["data"] == {
        CONF_HOST: "192.168.1.10",
        CONF_MODEL_NAME: "Model 60 L",
        CONF_SERIAL_NUMBER: "AIRFI-12345",
    }
    handler.async_set_unique_id.assert_awaited_once_with("airfi-12345")


@pytest.mark.unit
async def test_user_flow_shows_cannot_connect_error(hass) -> None:
    """Test that communication errors are mapped to the user-facing error key."""
    handler = AirfiConfigFlowHandler()
    handler.hass = hass
    handler.context = {"source": "user"}
    handler.flow_id = "test-flow"

    with patch(
        "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientCommunicationError("boom")),
    ):
        result = await handler.async_step_user(
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "AIRFI-12345",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.unit
async def test_user_flow_starts_discovery_immediately(hass) -> None:
    """Test that user flow starts discovery immediately when opened from the UI."""

    start_event: asyncio.Event = asyncio.Event()

    async def _pending_discovery() -> list:
        await start_event.wait()
        return []

    handler = AirfiConfigFlowHandler()
    handler.hass = hass
    handler.context = {"source": "user"}
    handler.flow_id = "test-flow"

    with patch.object(handler, "_async_run_discovery", side_effect=_pending_discovery):
        result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "discovering_devices"

    start_event.set()
    if handler.discovery_task is not None:
        await handler.discovery_task
