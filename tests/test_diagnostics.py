"""Test diagnostics for Airfi."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from custom_components.airfi.const import CONF_SERIAL_NUMBER, DOMAIN
from custom_components.airfi.coordinator.data_processing import AirfiDeviceData
from custom_components.airfi.data import AirfiData
from custom_components.airfi.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component


def _build_config_entry_with_runtime_data(hass) -> MockConfigEntry:
    """Build a config entry with runtime data for diagnostics tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_SERIAL_NUMBER: "AIRFI-12345",
        },
        options={"update_interval_seconds": 10},
        unique_id="airfi-12345",
        title="Airfi AIRFI-12345",
    )
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.update_interval = 10
    coordinator.data = AirfiDeviceData(
        firmware_version="3.8.1",
        modbus_register_version="3.0.0",
        model="Airfi",
        input_registers=[0] * 42,
        holding_registers=[0] * 59,
        lookup_registers=[],
    )
    coordinator.last_exception = None

    integration = MagicMock()
    integration.name = "Airfi"
    integration.version = "1.0.0-beta.2"
    integration.domain = DOMAIN
    integration.documentation = "https://github.com/janmilinds/ha-airfi"
    integration.issue_tracker = "https://github.com/janmilinds/ha-airfi/issues"

    client = MagicMock()

    entry.runtime_data = AirfiData(
        client=client,
        coordinator=coordinator,
        integration=integration,
    )
    return entry


@pytest.mark.unit
async def test_diagnostics_returns_expected_structure(hass) -> None:
    """Test that diagnostics returns all expected top-level keys."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert "entry" in result
    assert "integration" in result
    assert "coordinator" in result
    assert "modbus" in result
    assert "devices" in result
    assert "data_sample" in result
    assert "error" in result


@pytest.mark.unit
async def test_diagnostics_redacts_sensitive_data(hass) -> None:
    """Test that sensitive data is properly redacted in diagnostics."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Host and serial should be redacted
    assert result["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert result["entry"]["data"][CONF_SERIAL_NUMBER] == "**REDACTED**"


@pytest.mark.unit
async def test_diagnostics_includes_integration_info(hass) -> None:
    """Test that integration metadata is included."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["integration"]["name"] == "Airfi"
    assert result["integration"]["version"] == "1.0.0-beta.2"
    assert result["integration"]["domain"] == DOMAIN


@pytest.mark.unit
async def test_diagnostics_includes_coordinator_info(hass) -> None:
    """Test that coordinator state is included."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["data_keys"] is not None


@pytest.mark.unit
async def test_diagnostics_includes_data_sample(hass) -> None:
    """Test that sanitized data sample is included."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data_sample"]["firmware_version"] == "3.8.1"
    assert result["data_sample"]["modbus_register_version"] == "3.0.0"
    assert len(result["data_sample"]["input_registers"]) == 42
    assert len(result["data_sample"]["holding_registers"]) == 59


@pytest.mark.unit
async def test_diagnostics_includes_error_info_when_exception(hass) -> None:
    """Test that error info includes exception details."""
    entry = _build_config_entry_with_runtime_data(hass)
    entry.runtime_data.coordinator.last_exception = RuntimeError("test error")

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["error"]["last_exception"] == "test error"
    assert result["error"]["last_exception_type"] == "RuntimeError"


@pytest.mark.unit
async def test_diagnostics_error_info_none_when_no_exception(hass) -> None:
    """Test that error info is None when no exception."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["error"]["last_exception"] is None
    assert result["error"]["last_exception_type"] is None


@pytest.mark.unit
async def test_diagnostics_with_empty_coordinator_data(hass) -> None:
    """Test diagnostics when coordinator data is empty."""
    entry = _build_config_entry_with_runtime_data(hass)
    entry.runtime_data.coordinator.data = {}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data_sample"] == {}


@pytest.mark.unit
async def test_diagnostics_modbus_info(hass) -> None:
    """Test that modbus transport info is included."""
    entry = _build_config_entry_with_runtime_data(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["modbus"]["transport"] == "modbus_tcp"
    assert result["modbus"]["port"] == 502
    assert "host_configured" not in result["modbus"]


@pytest.mark.unit
async def test_diagnostics_includes_device_info(hass) -> None:
    """Test that diagnostics lists devices from the device registry."""
    entry = _build_config_entry_with_runtime_data(hass)

    # Register a device for this config entry
    device_reg = dr.async_get(hass)
    device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "AIRFI-12345")},
        manufacturer="Airfi",
        model="Model 60 L",
        name="Airfi AIRFI-12345",
        sw_version="3.8.1",
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert len(result["devices"]) == 1
    device = result["devices"][0]
    assert device["manufacturer"] == "Airfi"
    assert device["model"] == "Model 60 L"
    assert device["name"] == "Airfi AIRFI-12345"


@pytest.mark.integration
async def test_diagnostics_key_each_register_by_its_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> None:
    """Each raw register value appears under its own Modbus address, counted from 1."""
    data = mock_api.get_data.return_value
    data["input_registers"] = list(range(101, 101 + len(data["input_registers"])))
    data["holding_registers"] = list(range(201, 201 + len(data["holding_registers"])))
    assert await async_setup_component(hass, "diagnostics", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    sample = result["data_sample"]
    assert sample["input_registers"]["3x00001"] == 101
    assert sample["input_registers"]["3x00042"] == 142
    assert sample["holding_registers"]["4x00001"] == 201
    assert sample["holding_registers"]["4x00059"] == 259


@pytest.mark.integration
async def test_diagnostics_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """The downloaded diagnostics stay as recorded, so any new field shows up in review."""
    assert await async_setup_component(hass, "diagnostics", {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result == snapshot(exclude=paths("entry.entry_id", "devices.0.id", "integration.version"))
