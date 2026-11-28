"""Test the Airfi config flow."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.api import (
    AirfiApiClient,
    AirfiApiClientConnectionError,
    AirfiApiClientModbusError,
    AirfiApiClientNoResponseError,
)
from custom_components.airfi_home.config_flow_handler.config_flow import AirfiConfigFlowHandler
from custom_components.airfi_home.config_flow_handler.schemas import get_discovery_select_schema
from custom_components.airfi_home.const import (
    CONF_MODBUS_ID,
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_OPTION_MANUAL,
    DISCOVERY_OPTION_SCAN_MORE,
    DOMAIN,
    SECTION_ADVANCED,
)
from custom_components.airfi_home.utils.discovery import AirfiDiscoveredDevice, AirfiDiscoveryService
from custom_components.airfi_home.utils.error_mapping import map_connection_exception_to_error
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUPPORTED_UNIT_LOOKUP = [100, 310, 270]


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
    """Patch the network scan to find the given units; like a real scan, it does not finish at once."""

    async def _scan(**_kwargs: Any) -> list[AirfiDiscoveredDevice]:
        await asyncio.sleep(0)
        return list(devices)

    return patch.object(AirfiDiscoveryService, "async_scan", AsyncMock(side_effect=_scan))


async def _start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the setup from the UI and return the step shown once the scan has finished."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


def _reconfigure_input(host: str, modbus_id: int = 1) -> dict[str, Any]:
    """Return what the reconfigure form sends: the address, and the Modbus ID from its Advanced section."""
    return {CONF_HOST: host, SECTION_ADVANCED: {CONF_MODBUS_ID: modbus_id}}


async def _open_manual_form(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the setup from the UI, find nothing, and open the manual form."""
    with _scan_finds():
        result = await _start_user_flow(hass)
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})


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
    assert "scan" in result["menu_options"]
    assert "manual" in result["menu_options"]
    assert handler.discovery_task is None


@pytest.mark.unit
async def test_fallback_error_shows_menu(hass) -> None:
    """Test that fallback_error step shows menu with discovery and manual options."""
    handler = _make_handler(hass)
    handler.discovery_task = MagicMock()

    result = await handler.async_step_fallback_error()

    assert result["type"] is FlowResultType.MENU
    assert "scan" in result["menu_options"]
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
        patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)),
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
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id == "12345"
    assert entry.data == {
        CONF_HOST: "192.168.1.10",
        CONF_SERIAL_NUMBER: "12345",
        CONF_MODEL_NAME: "Model 100 L",
        CONF_MODBUS_ID: 1,
    }


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
@pytest.mark.parametrize(
    ("name", "title"),
    [
        pytest.param("", "Airfi Model 100 L", id="empty-name"),
        pytest.param("Upstairs", "Upstairs", id="typed-name"),
    ],
)
async def test_manual_setup_names_the_unit(hass: HomeAssistant, name: str, title: str) -> None:
    """A unit added by hand takes the typed name, or Airfi and its model when the name is left empty."""
    result = await _open_manual_form(hass)
    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: "12345", CONF_MODEL_NAME: "Model 100 L", CONF_NAME: name},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.title == title


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_manual_serial_is_keyed_like_an_announced_one(hass: HomeAssistant) -> None:
    """Leading zeros and surrounding spaces are dropped, so the unit gets the serial its announcement carries."""
    result = await _open_manual_form(hass)
    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: " 0012345 ", CONF_MODEL_NAME: "Model 100 L"},
        )
        await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id == "12345"
    assert entry.data[CONF_SERIAL_NUMBER] == "12345"


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_manual_serial_with_letters_is_refused_until_corrected(hass: HomeAssistant) -> None:
    """A serial that is not all digits shows an error on its field, and the corrected one adds the unit."""
    result = await _open_manual_form(hass)
    form = {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: "AIRFI-12345", CONF_MODEL_NAME: "Model 100 L"}
    with patch.object(
        AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)
    ) as test_connection:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_SERIAL_NUMBER: "invalid_serial"}
        test_connection.assert_not_awaited()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**form, CONF_SERIAL_NUMBER: "12345"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.integration
async def test_manual_serial_of_another_unit_at_the_address_is_refused(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A serial that differs from the one announced from the typed address is refused until it matches."""
    announce("192.168.1.60", 67890, 3)
    await hass.async_block_till_done()
    result = await _open_manual_form(hass)
    form = {CONF_HOST: "192.168.1.60", CONF_SERIAL_NUMBER: "11111", CONF_MODEL_NAME: "Model 100 L"}

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
        assert result["errors"] == {"base": "serial_mismatch"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**form, CONF_SERIAL_NUMBER: "67890"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "67890"


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_manual_setup_refuses_a_unit_whose_software_is_not_supported(hass: HomeAssistant) -> None:
    """A unit on register map 1.5 is refused with a reason, and a unit with supported software is then added."""
    result = await _open_manual_form(hass)
    form = {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: "12345", CONF_MODEL_NAME: "Model 100 L"}

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=[100, 381, 150])):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["errors"] == {"base": "unsupported_device"}

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
@pytest.mark.parametrize(
    ("error", "key"),
    [
        pytest.param(AirfiApiClientConnectionError("refused"), "cannot_connect", id="unreachable"),
        pytest.param(AirfiApiClientModbusError("bad response"), "cannot_retrieve_data", id="no-modbus-answer"),
    ],
)
async def test_manual_setup_recovers_from_a_failed_check(hass: HomeAssistant, error: Exception, key: str) -> None:
    """A failed connection check shows its error and keeps the typed values; the next attempt adds the unit."""
    result = await _open_manual_form(hass)
    form = {
        CONF_HOST: "192.168.1.10",
        CONF_SERIAL_NUMBER: "12345",
        CONF_MODEL_NAME: "Model 100 L",
        CONF_NAME: "Upstairs",
    }
    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(side_effect=error)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}
    suggested = {str(field): field.description for field in result["data_schema"].schema}
    assert suggested[CONF_NAME] == {"suggested_value": "Upstairs"}

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
    """A new address no unit was heard from is stored once confirmed, and the entry is set up again exactly once."""
    result = await init_integration.start_reconfigure_flow(hass)
    setups_before = mock_api.get_lookup_registers.await_count

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("10.0.0.1"))
    assert result["step_id"] == "reconfigure_unverified"
    assert result["description_placeholders"] == {"host": "10.0.0.1", "name": "Airfi Model 60 L"}
    assert init_integration.data[CONF_HOST] != "10.0.0.1"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert "translation_domain" not in result
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

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("10.0.0.1"))
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert "translation_domain" not in result
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
        AirfiApiClient, "async_get_lookup_registers", AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("10.0.0.1"))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert init_integration.data[CONF_HOST] == original_host


@pytest.mark.integration
@pytest.mark.parametrize(
    ("serial", "stored", "errors"),
    [
        pytest.param(12345678, True, None, id="same-unit"),
        pytest.param(67890, False, {"base": "wrong_device"}, id="other-unit"),
    ],
)
async def test_reconfigure_checks_which_unit_announced_from_the_address(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
    serial: int,
    stored: bool,
    errors: dict[str, str] | None,
) -> None:
    """The unit's own address is stored without confirmation; one another unit announced from is refused."""
    announce("10.0.0.1", serial)
    await hass.async_block_till_done()
    result = await init_integration.start_reconfigure_flow(hass)

    with patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("10.0.0.1"))
    await hass.async_block_till_done()

    assert result.get("errors") == errors
    assert (init_integration.data[CONF_HOST] == "10.0.0.1") is stored


# ---------------------------------------------------------------------------
# async_step_scan
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_searching_again_after_an_empty_search_lists_the_unit(hass: HomeAssistant) -> None:
    """Choosing to search again from the menu runs a new search and lists the unit it finds."""
    with _scan_finds():
        result = await _start_user_flow(hass)
    assert result["step_id"] == "fallback"

    with _scan_finds(_discovered_device()):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "scan"})
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["step_id"] == "discovery_select"
    assert result["description_placeholders"]["count"] == "1"


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
            "custom_components.airfi_home.config_flow_handler.validators.connection.validate_connection",
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
async def test_confirming_without_a_name_titles_the_unit_by_model(hass: HomeAssistant) -> None:
    """A unit confirmed with an empty name is titled after its model."""
    device = _discovered_device()

    with (
        _scan_finds(device),
        patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)),
    ):
        result = await _start_user_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": device.unique_key})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": ""})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.title == "Airfi Model 60 L"


@pytest.mark.unit
async def test_discovery_confirm_shows_error_on_failure(hass) -> None:
    """Test that connection failure during confirm shows form with error."""
    handler = _make_handler(hass)
    handler.selected_device = _discovered_device()

    with patch(
        "custom_components.airfi_home.config_flow_handler.validators.connection.validate_connection",
        new=AsyncMock(side_effect=AirfiApiClientConnectionError("timeout")),
    ):
        result = await handler.async_step_discovery_confirm(
            {"name": "Unit"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"host": "192.168.1.50", "serial": "12345", "model": "Model 60 L"}


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
        patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP)),
    ):
        result = await _start_user_flow(hass)
        assert result["step_id"] == "discovery_select"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": first.unique_key})
        assert result["step_id"] == "discovery_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Upstairs"})
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        (entry,) = hass.config_entries.async_entries(DOMAIN)
        assert entry.title == "Upstairs"
        assert entry.unique_id == "12345"
        assert entry.data == {
            CONF_HOST: "192.168.1.50",
            CONF_SERIAL_NUMBER: "12345",
            CONF_MODEL_NAME: "Model 60 L",
            CONF_MODBUS_ID: 1,
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

    existing_device = _discovered_device(serial=12345678)
    new_device = _discovered_device(host="192.168.1.99", serial=67890, model_id=3)

    with (
        patch.object(handler, "_async_current_entries", return_value=[config_entry]),
        patch(
            "custom_components.airfi_home.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
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
            "custom_components.airfi_home.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
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
            "custom_components.airfi_home.config_flow_handler.config_flow.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[new_device]),
        ),
    ):
        result = await handler._async_run_discovery()  # noqa: SLF001

    assert len(result) == 2
    serials = {d.serial for d in result}
    assert 11111 in serials
    assert 22222 in serials


# ---------------------------------------------------------------------------
# map_connection_exception_to_error
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(AirfiApiClientConnectionError("timeout"), "cannot_connect", id="unreachable"),
        pytest.param(AirfiApiClientNoResponseError("silent"), "no_response", id="no-answer"),
        pytest.param(AirfiApiClientModbusError("bad"), "cannot_retrieve_data", id="unreadable"),
        pytest.param(RuntimeError("unknown"), "cannot_connect", id="unexpected"),
    ],
)
def test_each_failure_has_its_form_error(exception: Exception, error: str) -> None:
    """Each kind of failed check is shown on the form with its own error."""
    assert map_connection_exception_to_error(exception) == error


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


# ---------------------------------------------------------------------------
# Modbus ID
# ---------------------------------------------------------------------------


def _default(schema: probatio.Schema, key: str) -> Any:
    """Return the value a form field is pre-filled with."""
    return next(marker.default() for marker in schema.schema if marker == key)


def _advanced(result: ConfigFlowResult) -> Any:
    """Return the reconfigure form's Advanced section."""
    return result["data_schema"].schema[SECTION_ADVANCED]


@pytest.mark.integration
async def test_unit_that_does_not_answer_is_added_once_its_modbus_id_is_entered(
    hass: HomeAssistant, modbus_unit: SimpleNamespace
) -> None:
    """A unit that is silent to ID 1 is asked for its ID, which is tried until the unit answers, and stored."""
    modbus_unit.modbus_id = 5
    result = await _open_manual_form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: "12345", CONF_MODEL_NAME: "Model 100 L"},
    )
    assert result["step_id"] == "modbus_id"
    assert result["errors"] == {}
    assert result["description_placeholders"] == {"host": "192.168.1.10"}
    assert _default(result["data_schema"], CONF_MODBUS_ID) == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MODBUS_ID: 7})
    assert result["step_id"] == "modbus_id"
    assert result["errors"] == {"base": "no_response"}
    assert _default(result["data_schema"], CONF_MODBUS_ID) == 7

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MODBUS_ID: 5})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data[CONF_MODBUS_ID] == 5
    assert entry.state is ConfigEntryState.LOADED
    assert modbus_unit.connection.read_holding_registers.call_args.kwargs["device_id"] == 5


@pytest.mark.integration
async def test_found_unit_that_does_not_answer_is_asked_for_its_modbus_id(
    hass: HomeAssistant, modbus_unit: SimpleNamespace
) -> None:
    """Confirming a found unit that is silent to ID 1 asks for its ID before the unit is added under its name."""
    modbus_unit.modbus_id = 12
    device = _discovered_device()
    with _scan_finds(device):
        result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": device.unique_key})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: "Upstairs"})
    assert result["step_id"] == "modbus_id"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MODBUS_ID: 12})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.title == "Upstairs"
    assert entry.data[CONF_MODBUS_ID] == 12


@pytest.mark.integration
async def test_unit_that_cannot_be_reached_is_not_asked_for_a_modbus_id(
    hass: HomeAssistant, modbus_unit: SimpleNamespace
) -> None:
    """Without a connection the ID cannot be the cause, so the address form shows the error instead."""
    modbus_unit.connection.connect.return_value = False
    result = await _open_manual_form(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.10", CONF_SERIAL_NUMBER: "12345", CONF_MODEL_NAME: "Model 100 L"},
    )

    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.integration
async def test_reconfigure_tries_the_modbus_id_from_the_advanced_section(
    hass: HomeAssistant, modbus_unit: SimpleNamespace, config_entry: MockConfigEntry
) -> None:
    """The stored ID is pre-filled; an ID the unit ignores opens the section with the error; 1 is accepted."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    result = await config_entry.start_reconfigure_flow(hass)
    assert _advanced(result).options["collapsed"] is True
    assert _default(_advanced(result).schema, CONF_MODBUS_ID) == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("192.168.1.10", 5))
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "no_response"}
    assert _advanced(result).options["collapsed"] is False
    assert _default(_advanced(result).schema, CONF_MODBUS_ID) == 5
    assert config_entry.data[CONF_HOST] == "192.168.1.10"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], _reconfigure_input("192.168.1.10", 1))
    assert result["step_id"] == "reconfigure_unverified"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_MODBUS_ID] == 1
    assert config_entry.state is ConfigEntryState.LOADED
