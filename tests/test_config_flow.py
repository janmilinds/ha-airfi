"""Test the Airfi config flow."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.api import AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.config_flow_handler.config_flow import AirfiConfigFlowHandler
from custom_components.airfi.config_flow_handler.options_flow import AirfiOptionsFlow
from custom_components.airfi.const import CONF_MODEL_NAME, CONF_SERIAL_NUMBER, DOMAIN
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice
from homeassistant.const import CONF_HOST
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


# ---------------------------------------------------------------------------
# async_step_user (manual path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_user_flow_creates_entry(hass) -> None:
    """Test that the user flow creates an entry with host and serial number."""
    handler = _make_handler(hass)

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
async def test_user_flow_shows_fallback_when_discovery_fails(hass) -> None:
    """Test that a failed discovery shows fallback menu."""
    handler = _make_handler(hass)

    done_task: asyncio.Future[list] = hass.loop.create_future()
    done_task.set_exception(OSError("socket error"))
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


@pytest.mark.unit
async def test_manual_step_creates_entry_on_success(hass) -> None:
    """Test that manual step creates an entry after successful validation."""
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
                CONF_MODEL_NAME: "Model 100 L",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.10"
    assert result["data"][CONF_SERIAL_NUMBER] == "12345"


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


@pytest.mark.unit
async def test_reconfigure_shows_form(hass, config_entry) -> None:
    """Test that reconfigure shows a prefilled form."""
    handler = _make_handler(hass)
    handler.context = {"source": "reconfigure"}

    with patch.object(handler, "_get_reconfigure_entry", return_value=config_entry):
        result = await handler.async_step_reconfigure()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


@pytest.mark.unit
async def test_reconfigure_updates_entry_on_success(hass, config_entry) -> None:
    """Test that reconfigure updates the config entry with a new host."""
    handler = _make_handler(hass)

    with (
        patch.object(handler, "_get_reconfigure_entry", return_value=config_entry),
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(handler, "async_update_reload_and_abort", return_value={"type": "abort"}) as mock_update,
    ):
        result = await handler.async_step_reconfigure(
            {CONF_HOST: "10.0.0.1"},
        )

    mock_update.assert_called_once()
    assert result == {"type": "abort"}


@pytest.mark.unit
async def test_reconfigure_shows_error_on_failure(hass, config_entry) -> None:
    """Test that reconfiguration failure shows form with error."""
    handler = _make_handler(hass)

    with (
        patch.object(handler, "_get_reconfigure_entry", return_value=config_entry),
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(side_effect=AirfiApiClientConnectionError("timeout")),
        ),
    ):
        result = await handler.async_step_reconfigure(
            {CONF_HOST: "bad-host"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


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
    """Test that selecting __manual__ goes to manual step."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    result = await handler.async_step_discovery_select(
        {"device": "__manual__"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


@pytest.mark.unit
async def test_discovery_select_scan_more(hass) -> None:
    """Test that selecting __scan_more__ resets and re-scans."""
    handler = _make_handler(hass)
    handler.discovered_devices = [_discovered_device()]

    start_event = asyncio.Event()

    async def _pending() -> list:
        await start_event.wait()
        return []

    with patch.object(handler, "_async_run_discovery", side_effect=_pending):
        result = await handler.async_step_discovery_select(
            {"device": "__scan_more__"},
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


@pytest.mark.unit
async def test_discovery_confirm_creates_entry(hass) -> None:
    """Test that confirming a device creates an entry."""
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
            {"name": "My Airfi Unit"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Airfi Unit"
    assert result["data"][CONF_HOST] == "192.168.1.50"
    assert result["data"][CONF_SERIAL_NUMBER] == 12345


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


@pytest.mark.unit
async def test_discovery_confirm_cascades_to_next_device(hass) -> None:
    """Test that confirming with remaining devices cascades to next selection."""
    device1 = _discovered_device(host="192.168.1.50", serial=12345)
    device2 = _discovered_device(host="192.168.1.51", serial=67890, model_id=3)
    handler = _make_handler(hass)
    handler.selected_device = device1
    handler.discovered_devices = [device1, device2]

    with (
        patch(
            "custom_components.airfi.config_flow_handler.config_flow.validate_connection",
            new=AsyncMock(return_value=None),
        ),
        patch.object(AirfiConfigFlowHandler, "_abort_if_unique_id_configured", return_value=None),
    ):
        result = await handler.async_step_discovery_confirm(
            {"name": "Unit 1"},
        )

    # Should show the discovery_select form for the remaining device
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_select"
    assert len(handler.discovered_devices) == 1
    assert handler.discovered_devices[0] is device2


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
