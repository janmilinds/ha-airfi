"""Tests for the Airfi repairs module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.airfi.api.client import AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.const import DOMAIN, ISSUE_DEVICE_UNREACHABLE
from custom_components.airfi.repairs import DeviceUnreachableRepairFlow, async_create_fix_flow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.unit
async def test_async_create_fix_flow_returns_device_unreachable_flow(hass, config_entry) -> None:
    """Test that a device_unreachable issue_id returns a DeviceUnreachableRepairFlow."""
    config_entry.add_to_hass(hass)
    issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"

    flow = await async_create_fix_flow(hass, issue_id, None)

    assert isinstance(flow, DeviceUnreachableRepairFlow)


@pytest.mark.unit
async def test_async_create_fix_flow_raises_for_unknown_entry_id(hass) -> None:
    """Test that a device_unreachable issue with an unknown entry_id raises ValueError."""
    issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_nonexistent_entry"

    with pytest.raises(ValueError, match="Unknown config entry in issue ID"):
        await async_create_fix_flow(hass, issue_id, None)


@pytest.mark.unit
async def test_async_create_fix_flow_raises_for_unknown_issue_id(hass) -> None:
    """Test that an unrecognised issue_id raises ValueError."""
    with pytest.raises(ValueError, match="Unknown issue ID"):
        await async_create_fix_flow(hass, "some_completely_unknown_issue", None)


@pytest.mark.unit
async def test_async_step_init_shows_form_without_user_input(hass, config_entry) -> None:
    """Test that the init step shows the form when no user input is provided."""
    flow = DeviceUnreachableRepairFlow(config_entry)
    flow.hass = hass
    flow.flow_id = "test-flow"
    flow.issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"

    result = await flow.async_step_init(user_input=None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}


@pytest.mark.unit
async def test_async_step_init_updates_host_and_reloads_on_success(hass, config_entry) -> None:
    """Test that a valid host updates the entry, deletes the issue, and reloads the entry."""
    config_entry.add_to_hass(hass)
    flow = DeviceUnreachableRepairFlow(config_entry)
    flow.hass = hass
    flow.flow_id = "test-flow"
    flow.issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"

    with (
        patch(
            "custom_components.airfi.repairs.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch("custom_components.airfi.repairs.ir.async_delete_issue") as mock_delete_issue,
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as mock_reload,
    ):
        result = await flow.async_step_init(user_input={CONF_HOST: "10.0.0.1"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.data[CONF_HOST] == "10.0.0.1"
    mock_delete_issue.assert_called_once_with(hass, DOMAIN, flow.issue_id)
    mock_reload.assert_awaited_once_with(config_entry.entry_id)


@pytest.mark.unit
async def test_async_step_init_shows_cannot_connect_on_connection_error(hass, config_entry) -> None:
    """Test that a TCP connection error maps to the cannot_connect error key."""
    flow = DeviceUnreachableRepairFlow(config_entry)
    flow.hass = hass
    flow.flow_id = "test-flow"
    flow.issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"

    with patch(
        "custom_components.airfi.repairs.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientConnectionError("timeout")),
    ):
        result = await flow.async_step_init(user_input={CONF_HOST: "10.0.0.1"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.unit
async def test_async_step_init_shows_cannot_retrieve_data_on_modbus_error(hass, config_entry) -> None:
    """Test that a Modbus error maps to the cannot_retrieve_data error key."""
    flow = DeviceUnreachableRepairFlow(config_entry)
    flow.hass = hass
    flow.flow_id = "test-flow"
    flow.issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"

    with patch(
        "custom_components.airfi.repairs.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientModbusError("read failed")),
    ):
        result = await flow.async_step_init(user_input={CONF_HOST: "10.0.0.1"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve_data"}
