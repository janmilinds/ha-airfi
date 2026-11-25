"""Tests for the Airfi repairs module."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.airfi.api import AirfiApiClient
from custom_components.airfi.api.client import AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.const import DOMAIN, ISSUE_DEVICE_UNREACHABLE
from custom_components.airfi.repairs import DeviceUnreachableRepairFlow, async_create_fix_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


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


@pytest.fixture
async def repair_issue(hass: HomeAssistant, init_integration: MockConfigEntry) -> str:
    """Raise the unreachable-device issue for the loaded entry and return its ID."""
    assert await async_setup_component(hass, "repairs", {})
    issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{init_integration.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DEVICE_UNREACHABLE,
        translation_placeholders={"name": init_integration.title},
    )
    return issue_id


@pytest.mark.integration
async def test_repair_form_opens_without_an_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    repair_issue: str,
) -> None:
    """Opening the repair shows the address form with the current address and no error yet."""
    result = await start_repair_fix_flow(await hass_client(), DOMAIN, repair_issue)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}
    assert result["data_schema"][0]["default"] == init_integration.data[CONF_HOST]


@pytest.mark.integration
async def test_repair_saves_the_new_address_and_reloads(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    init_integration: MockConfigEntry,
    repair_issue: str,
) -> None:
    """A reachable new address is stored, the issue goes away and the entry loads again."""
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, repair_issue)

    with patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)):
        result = await process_repair_fix_flow(client, flow["flow_id"], {CONF_HOST: "10.0.0.1"})
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert init_integration.data[CONF_HOST] == "10.0.0.1"
    assert issue_registry.async_get_issue(DOMAIN, repair_issue) is None
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.integration
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(AirfiApiClientConnectionError("timeout"), "cannot_connect", id="unreachable"),
        pytest.param(AirfiApiClientModbusError("read failed"), "cannot_retrieve_data", id="no-data"),
    ],
)
async def test_repair_keeps_the_address_when_the_new_one_fails(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    init_integration: MockConfigEntry,
    repair_issue: str,
    error: Exception,
    expected: str,
) -> None:
    """A new address that does not answer shows why, and nothing is stored."""
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, repair_issue)

    with patch.object(AirfiApiClient, "async_test_connection", AsyncMock(side_effect=error)):
        result = await process_repair_fix_flow(client, flow["flow_id"], {CONF_HOST: "10.0.0.1"})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert init_integration.data[CONF_HOST] == "192.168.1.10"
    assert issue_registry.async_get_issue(DOMAIN, repair_issue) is not None
