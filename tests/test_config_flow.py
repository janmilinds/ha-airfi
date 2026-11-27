"""Test the Airfi config flow."""

import asyncio
from contextlib import AbstractContextManager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi.api import AirfiApiClient, AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.config_flow_handler.config_flow import AirfiConfigFlowHandler
from custom_components.airfi.config_flow_handler.options_flow import AirfiOptionsFlow
from custom_components.airfi.config_flow_handler.schemas import get_discovery_select_schema
from custom_components.airfi.const import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_OPTION_MANUAL,
    DISCOVERY_OPTION_SCAN_MORE,
    DOMAIN,
)
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice, AirfiDiscoveryService
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_handler(hass) -> AirfiConfigFlowHandler:
    """Create a config flow handler ready for testing."""
    handler = AirfiConfigFlowHandler()
    handler.hass = hass
    handler.context = {"source": "user"}
    handler.flow_id = "test-flow"
    handler.async_set_unique_id = AsyncMock()
    return handler


def _discovered_device(
    host: str = "192.168.1.50",
    serial: int = 12345,
    model_id: int = 1,
) -> AirfiDiscoveredDevice:
    """Create a test discovery device."""
    return AirfiDiscoveredDevice(host=host, serial=serial, model_id=model_id)


def _scan_finds(*devices: AirfiDiscoveredDevice) -> AbstractContextManager[AsyncMock]:
    """Patch the network scan to find the given units."""
    return patch.object(AirfiDiscoveryService, "async_scan", AsyncMock(return_value=list(devices)))


async def _start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the setup from the UI and return the step shown once the scan has finished."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


# ---------------------------------------------------------------------------
# async_step_user (manual path)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_user_flow_with_input_adds_the_unit(hass: HomeAssistant) -> None:
    """A setup started with the address and serial adds the unit under its serial."""
    with patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "AIRFI-12345",
                CONF_MODEL_NAME: "Model 60 L",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Airfi Model 60 L"
    assert entries[0].unique_id == "airfi-12345"
    assert entries[0].data == {
        CONF_HOST: "192.168.1.10",
        CONF_MODEL_NAME: "Model 60 L",
        CONF_SERIAL_NUMBER: "AIRFI-12345",
    }


@pytest.mark.unit
async def test_user_flow_shows_cannot_connect_error(hass) -> None:
    """Test that a TCP connection error is mapped to the cannot_connect error key."""
    handler = _make_handler(hass)

    with patch(
        "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientConnectionError("timeout")),
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
async def test_user_flow_shows_cannot_retrieve_data_error(hass) -> None:
    """Test that a Modbus protocol error maps to cannot_retrieve_data."""
    handler = _make_handler(hass)

    with patch(
        "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientModbusError("bad response")),
    ):
        result = await handler.async_step_user(
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "AIRFI-12345",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_retrieve_data"}


# ---------------------------------------------------------------------------
# async_step_user (discovery path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_user_flow_starts_discovery_immediately(hass) -> None:
    """Test that user flow starts discovery immediately when opened from the UI."""
    start_event: asyncio.Event = asyncio.Event()

    async def _pending_discovery() -> list:
        await start_event.wait()
        return []

    handler = _make_handler(hass)

    with patch.object(handler, "_async_run_discovery", side_effect=_pending_discovery):
        result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "discovering_devices"

    start_event.set()
    if handler.discovery_task is not None:
        await handler.discovery_task


@pytest.mark.unit
async def test_user_flow_shows_discovery_select_when_devices_found(hass) -> None:
    """Test that discovery results show the device selection step."""
    handler = _make_handler(hass)
    device = _discovered_device()

    done_task: asyncio.Future[list] = hass.loop.create_future()
    done_task.set_result([device])
    handler.discovery_task = done_task
    handler.discovered_devices = [device]

    result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "discovery_select"


@pytest.mark.unit
async def test_user_flow_shows_fallback_when_no_devices(hass) -> None:
    """Test that discovery with no results shows fallback menu."""
    handler = _make_handler(hass)

    done_task: asyncio.Future[list] = hass.loop.create_future()
    done_task.set_result([])
    handler.discovery_task = done_task
    handler.discovered_devices = []

    result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "fallback"


@pytest.mark.unit
async def test_user_flow_shows_fallback_error_when_socket_fails(hass) -> None:
    """Test that a socket error in discovery shows the socket error fallback."""
    handler = _make_handler(hass)

    done_task: asyncio.Future[list] = hass.loop.create_future()
    done_task.set_exception(OSError("socket error"))
    handler.discovery_task = done_task

    result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "fallback_error"


@pytest.mark.unit
async def test_user_flow_shows_fallback_when_discovery_fails_non_os_error(hass) -> None:
    """Test that a non-OSError discovery failure shows the normal fallback."""
    handler = _make_handler(hass)

    done_task: asyncio.Future[list] = hass.loop.create_future()
    done_task.set_exception(RuntimeError("unexpected discovery error"))
    handler.discovery_task = done_task

    result = await handler.async_step_user()

    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "fallback"


# ---------------------------------------------------------------------------
# async_step_fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_fallback_shows_menu(hass) -> None:
    """Test that fallback step shows menu with discovery and manual options."""
    handler = _make_handler(hass)
    handler.discovery_task = MagicMock()

    result = await handler.async_step_fallback()

    assert result["type"] is FlowResultType.MENU
    assert "discovery" in result["menu_options"]
    assert "manual" in result["menu_options"]
    assert handler.discovery_task is None


@pytest.mark.unit
async def test_fallback_error_shows_menu(hass) -> None:
    """Test that fallback_error step shows menu with discovery and manual options."""
    handler = _make_handler(hass)
    handler.discovery_task = MagicMock()

    result = await handler.async_step_fallback_error()

    assert result["type"] is FlowResultType.MENU
    assert "discovery" in result["menu_options"]
    assert "manual" in result["menu_options"]
    assert handler.discovery_task is None


# ---------------------------------------------------------------------------
# async_step_manual
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_manual_step_shows_form_without_input(hass) -> None:
    """Test that manual step shows a form when no user input provided."""
    handler = _make_handler(hass)

    result = await handler.async_step_manual()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_manual_setup_after_an_empty_scan_adds_the_unit(hass: HomeAssistant) -> None:
    """When the scan finds nothing, the unit entered by hand is added."""
    with (
        _scan_finds(),
        patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)),
    ):
        result = await _start_user_flow(hass)
        assert result["step_id"] == "fallback"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
        assert result["step_id"] == "manual"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "12345",
                CONF_MODEL_NAME: "Model 100 L",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "12345"
    assert entries[0].data == {
        CONF_HOST: "192.168.1.10",
        CONF_SERIAL_NUMBER: "12345",
        CONF_MODEL_NAME: "Model 100 L",
    }


@pytest.mark.unit
async def test_manual_step_uses_default_model_name(hass) -> None:
    """Test that manual step defaults to 'Airfi' when model name is omitted."""
    handler = _make_handler(hass)

    with (
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(AirfiConfigFlowHandler, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await handler.async_step_manual(
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "12345",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MODEL_NAME] == "Airfi"
    assert result["title"] == "Airfi 12345"


@pytest.mark.unit
async def test_manual_step_shows_error_on_connection_failure(hass) -> None:
    """Test that manual step shows form with error when connection fails."""
    handler = _make_handler(hass)

    with patch(
        "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientConnectionError("refused")),
    ):
        result = await handler.async_step_manual(
            {
                CONF_HOST: "192.168.1.10",
                CONF_SERIAL_NUMBER: "12345",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# ---------------------------------------------------------------------------
# async_step_reconfigure
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_reconfigure_shows_the_current_address(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Reconfiguring opens a form prefilled with the address the entry uses now."""
    result = await init_integration.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}


@pytest.mark.integration
async def test_reconfigure_sets_a_loaded_entry_up_once(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_api: SimpleNamespace,
    init_integration: MockConfigEntry,
) -> None:
    """A new address is stored and the running entry is set up again exactly once."""
    result = await init_integration.start_reconfigure_flow(hass)
    setups_before = mock_api.get_lookup_registers.await_count

    with patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "10.0.0.1"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.data[CONF_HOST] == "10.0.0.1"
    assert init_integration.state is ConfigEntryState.LOADED
    assert mock_api.get_lookup_registers.await_count == setups_before + 1
    assert "should use it for scheduling a reload" not in caplog.text


@pytest.mark.integration
async def test_reconfigure_sets_up_an_entry_that_is_retrying(
    hass: HomeAssistant,
    mock_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> None:
    """An entry waiting to retry setup loads at once with the new address."""
    mock_api.get_data.side_effect = AirfiApiClientModbusError("illegal")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_api.get_data.side_effect = None
    result = await config_entry.start_reconfigure_flow(hass)

    with patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)):
        await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "10.0.0.1"})
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.integration
async def test_reconfigure_keeps_the_address_when_the_new_one_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A new address that does not answer shows why, and nothing is stored."""
    original_host = init_integration.data[CONF_HOST]
    result = await init_integration.start_reconfigure_flow(hass)

    with patch.object(
        AirfiApiClient, "async_test_connection", AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: "10.0.0.1"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert init_integration.data[CONF_HOST] == original_host


# ---------------------------------------------------------------------------
# async_step_discovery
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_discovery_resets_state_and_triggers_user(hass) -> None:
    """Test that the discovery step resets state and delegates to user step."""
    handler = _make_handler(hass)
    handler.discovery_task = MagicMock()
    handler.discovered_devices = [_discovered_device()]
    handler.selected_device = _discovered_device()

    start_event = asyncio.Event()

    async def _pending() -> list:
        await start_event.wait()
        return []

    with patch.object(handler, "_async_run_discovery", side_effect=_pending):
        result = await handler.async_step_discovery()

    assert handler.discovered_devices == []
    assert handler.selected_device is None
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    start_event.set()
    if handler.discovery_task is not None:
        await handler.discovery_task


# ---------------------------------------------------------------------------
# async_step_discovery_select
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_discovery_select_shows_form(hass) -> None:
    """Test that discovery_select shows a selection form."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    result = await handler.async_step_discovery_select()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_select"


@pytest.mark.unit
async def test_discovery_select_picks_device(hass) -> None:
    """Test that selecting a device moves to confirmation."""
    device = _discovered_device()
    handler = _make_handler(hass)
    handler.discovered_devices = [device]

    with (
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await handler.async_step_discovery_select(
            {"device": device.unique_key},
        )

    assert handler.selected_device is device
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


@pytest.mark.unit
async def test_discovery_select_manual_option(hass) -> None:
    """Test that selecting the manual option goes to manual step."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    result = await handler.async_step_discovery_select(
        {"device": DISCOVERY_OPTION_MANUAL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.unit
async def test_discovery_select_scan_more(hass) -> None:
    """Test that selecting the search-for-more option scans again and keeps the devices already found."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    start_event = asyncio.Event()

    async def _pending() -> list:
        await start_event.wait()
        return []

    with patch.object(handler, "_async_run_discovery", side_effect=_pending):
        result = await handler.async_step_discovery_select(
            {"device": DISCOVERY_OPTION_SCAN_MORE},
        )

    assert handler._discovery_accumulate is True  # noqa: SLF001
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    start_event.set()
    if handler.discovery_task is not None:
        await handler.discovery_task


@pytest.mark.unit
async def test_discovery_select_invalid_key_aborts(hass) -> None:
    """Test that selecting a non-existent device key aborts the flow."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    result = await handler.async_step_discovery_select(
        {"device": "nonexistent_key"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_selection"


# ---------------------------------------------------------------------------
# async_step_discovery_confirm
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_discovery_confirm_shows_form(hass) -> None:
    """Test that confirmation step shows form with device details."""
    handler = _make_handler(hass)
    handler.selected_device = _discovered_device()

    result = await handler.async_step_discovery_confirm()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["host"] == "192.168.1.50"
    assert result["description_placeholders"]["serial"] == "12345"


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_confirming_the_only_found_unit_adds_it(hass: HomeAssistant) -> None:
    """Selecting and confirming the one unit found adds it under the given name."""
    device = _discovered_device()

    with (
        _scan_finds(device),
        patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)),
    ):
        result = await _start_user_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": device.unique_key})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "My Airfi Unit"})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "My Airfi Unit"
    assert entries[0].unique_id == "12345"
    assert entries[0].data == {
        CONF_HOST: "192.168.1.50",
        CONF_SERIAL_NUMBER: 12345,
        CONF_MODEL_NAME: "Model 60 L",
    }


@pytest.mark.unit
async def test_discovery_confirm_uses_default_name(hass) -> None:
    """Test that confirming without a name uses the model name."""
    handler = _make_handler(hass)
    handler.selected_device = _discovered_device()
    handler.discovered_devices = [handler.selected_device]

    with (
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(AirfiConfigFlowHandler, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await handler.async_step_discovery_confirm(
            {"name": ""},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airfi Model 60 L"


@pytest.mark.unit
async def test_discovery_confirm_shows_error_on_failure(hass) -> None:
    """Test that connection failure during confirm shows form with error."""
    handler = _make_handler(hass)
    handler.selected_device = _discovered_device()

    with patch(
        "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientConnectionError("timeout")),
    ):
        result = await handler.async_step_discovery_confirm(
            {"name": "Unit"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.unit
async def test_discovery_confirm_aborts_without_selected_device(hass) -> None:
    """Test that confirming without a selected device aborts."""
    handler = _make_handler(hass)
    handler.selected_device = None

    result = await handler.async_step_discovery_confirm()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_selection"


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_confirming_one_of_two_found_units_adds_it(hass: HomeAssistant) -> None:
    """The confirmed unit is added, and the next setup offers only the other one."""
    first = _discovered_device(host="192.168.1.50", serial=12345)
    second = _discovered_device(host="192.168.1.51", serial=67890, model_id=3)

    with (
        _scan_finds(first, second),
        patch.object(AirfiApiClient, "async_test_connection", AsyncMock(return_value=None)),
    ):
        result = await _start_user_flow(hass)
        assert result["step_id"] == "discovery_select"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": first.unique_key})
        assert result["step_id"] == "discovery_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Upstairs"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].title == "Upstairs"
        assert entries[0].unique_id == "12345"
        assert entries[0].data == {
            CONF_HOST: "192.168.1.50",
            CONF_SERIAL_NUMBER: 12345,
            CONF_MODEL_NAME: "Model 60 L",
        }

        result = await _start_user_flow(hass)

    device_row, *_ = result["data_schema"].schema["device"].config["options"]
    assert result["description_placeholders"]["count"] == "1"
    assert device_row["value"] == second.unique_key


# ---------------------------------------------------------------------------
# _async_run_discovery
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_run_discovery_filters_already_configured(hass, config_entry) -> None:
    """Test that already-configured serials are excluded from discovery results."""
    config_entry.add_to_hass(hass)
    handler = _make_handler(hass)

    # Config entry has serial "AIRFI-12345" — discovered device must match that string
    existing_device = _discovered_device(serial="AIRFI-12345")
    new_device = _discovered_device(host="192.168.1.99", serial=67890, model_id=3)

    with (
        patch.object(handler, "_async_current_entries", return_value=[config_entry]),
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[existing_device, new_device]),
        ),
    ):
        result = await handler._async_run_discovery()  # noqa: SLF001

    # Only the new device should remain
    assert len(result) == 1
    assert result[0].serial == 67890


@pytest.mark.unit
async def test_run_discovery_fallback_scan(hass) -> None:
    """Test that a second scan runs when the first returns empty."""
    handler = _make_handler(hass)
    device = _discovered_device()

    with (
        patch.object(handler, "_async_current_entries", return_value=[]),
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
            new=AsyncMock(side_effect=[[], [device]]),
        ),
    ):
        result = await handler._async_run_discovery()  # noqa: SLF001

    assert len(result) == 1
    assert result[0] is device


@pytest.mark.unit
async def test_run_discovery_accumulate_mode(hass) -> None:
    """Test that accumulate mode preserves previously discovered devices."""
    handler = _make_handler(hass)
    old_device = _discovered_device(serial=11111)
    new_device = _discovered_device(host="192.168.1.60", serial=22222, model_id=3)
    handler.discovered_devices = [old_device]
    handler._discovery_accumulate = True  # noqa: SLF001

    with (
        patch.object(handler, "_async_current_entries", return_value=[]),
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[new_device]),
        ),
    ):
        result = await handler._async_run_discovery()  # noqa: SLF001

    assert len(result) == 2
    serials = {d.serial for d in result}
    assert 11111 in serials
    assert 22222 in serials


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_options_flow_shows_form(hass, config_entry) -> None:
    """Test that options flow shows a form with current options."""
    config_entry.add_to_hass(hass)
    flow = AirfiOptionsFlow()
    flow.hass = hass
    flow.handler = config_entry.entry_id
    flow.flow_id = "test-flow"
    flow._options_flow_lock = asyncio.Lock()  # noqa: SLF001

    result = await flow.async_step_init()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


@pytest.mark.unit
async def test_options_flow_creates_entry(hass, config_entry) -> None:
    """Test that options flow creates entry with user-provided values."""
    config_entry.add_to_hass(hass)
    flow = AirfiOptionsFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "test-flow"
    flow._options_flow_lock = asyncio.Lock()  # noqa: SLF001

    result = await flow.async_step_init({"update_interval_seconds": 30})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["update_interval_seconds"] == 30


# ---------------------------------------------------------------------------
# async_get_options_flow
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_options_flow_returns_options_flow(hass, config_entry) -> None:
    """Test that async_get_options_flow returns an AirfiOptionsFlow instance."""
    result = AirfiConfigFlowHandler.async_get_options_flow(config_entry)

    assert isinstance(result, AirfiOptionsFlow)


# ---------------------------------------------------------------------------
# _map_exception_to_error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_map_exception_to_error_connection(hass) -> None:
    """Test that connection errors map to cannot_connect."""
    handler = _make_handler(hass)
    result = handler._map_exception_to_error(AirfiApiClientConnectionError("timeout"))  # noqa: SLF001
    assert result == "cannot_connect"


@pytest.mark.unit
def test_map_exception_to_error_modbus(hass) -> None:
    """Test that Modbus errors map to cannot_retrieve_data."""
    handler = _make_handler(hass)
    result = handler._map_exception_to_error(AirfiApiClientModbusError("bad"))  # noqa: SLF001
    assert result == "cannot_retrieve_data"


@pytest.mark.unit
def test_map_exception_to_error_generic(hass) -> None:
    """Test that generic exceptions map to cannot_connect."""
    handler = _make_handler(hass)
    result = handler._map_exception_to_error(RuntimeError("unknown"))  # noqa: SLF001
    assert result == "cannot_connect"


@pytest.mark.unit
def test_device_list_shows_no_untranslated_text() -> None:
    """Test that the device list's own options are translated and a device row carries no English words."""
    device = AirfiDiscoveredDevice(host="192.168.1.10", serial=12345678, model_id=1)
    config = get_discovery_select_schema([device]).schema["device"].config
    strings = json.loads(
        (Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations" / "en.json").read_text("utf-8")
    )
    translated = strings["selector"][config["translation_key"]]["options"]

    device_row, *own_options = config["options"]

    assert device_row["label"] == "Airfi Model 60 L · 192.168.1.10 · 12345678"
    assert [option["value"] for option in own_options] == [DISCOVERY_OPTION_SCAN_MORE, DISCOVERY_OPTION_MANUAL]
    assert all(option["value"] in translated for option in own_options)
