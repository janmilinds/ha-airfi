"""Test the Airfi config flow for units found without the user starting a setup."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.api import AirfiApiClient
from custom_components.airfi_home.const import CONF_MODBUS_ID, CONF_MODEL_NAME, CONF_SERIAL_NUMBER, DOMAIN
from custom_components.airfi_home.utils.discovery import AirfiDiscoveredDevice, AirfiDiscoveryService
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

UNIT = AirfiDiscoveredDevice(host="192.168.1.60", serial=67890, model_id=3)

SUPPORTED_UNIT_LOOKUP = [100, 310, 270]


def _scan_finds(*devices: AirfiDiscoveredDevice) -> AbstractContextManager[AsyncMock]:
    """Patch the network scan to find the given units; like a real scan, it does not finish at once."""

    async def _scan(**_kwargs: Any) -> list[AirfiDiscoveredDevice]:
        await asyncio.sleep(0)
        return list(devices)

    return patch.object(AirfiDiscoveryService, "async_scan", AsyncMock(side_effect=_scan))


def _connection_works() -> AbstractContextManager[AsyncMock]:
    """Patch the connection check to pass."""
    return patch.object(AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=SUPPORTED_UNIT_LOOKUP))


async def _dhcp_sees(hass: HomeAssistant, ip: str, macaddress: str = "bc974070a1b2") -> ConfigFlowResult:
    """Start the flow Home Assistant opens when its DHCP watcher sees a matching device."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(ip=ip, hostname="", macaddress=macaddress),
    )


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_unit_seen_by_dhcp_is_added_once_confirmed(hass: HomeAssistant) -> None:
    """A unit with an Airfi MAC address that announces itself from the same address is offered and added."""
    with _scan_finds(UNIT):
        result = await _dhcp_sees(hass, UNIT.host)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"host": UNIT.host, "serial": "67890", "model": "Model 100 L"}

    with _connection_works():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: ""})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.unique_id == "67890"
    assert entry.title == "Airfi Model 100 L"
    assert entry.data == {
        CONF_HOST: UNIT.host,
        CONF_SERIAL_NUMBER: "67890",
        CONF_MODEL_NAME: "Model 100 L",
        CONF_MODBUS_ID: 1,
    }


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_unit_of_a_model_not_in_the_table_is_added_as_airfi(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A unit whose model ID the table lacks is named Airfi and gets no model, rather than an English placeholder."""
    unit = AirfiDiscoveredDevice(host="192.168.1.61", serial=67891, model_id=39)
    with _scan_finds(unit):
        result = await _dhcp_sees(hass, unit.host)

    assert result["description_placeholders"] == {"host": unit.host, "serial": "67891", "model": "Airfi"}

    with _connection_works():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: ""})
        await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.title == "Airfi"
    assert entry.data == {CONF_HOST: unit.host, CONF_SERIAL_NUMBER: "67891", CONF_MODBUS_ID: 1}
    device = device_registry.async_get_device_by_identifier((DOMAIN, "67891"), entry.entry_id)
    assert device is not None
    assert device.model is None


@pytest.mark.integration
@pytest.mark.parametrize(
    ("macaddress", "found"),
    [
        pytest.param("bc974010a1b2", [UNIT], id="other-vendor-in-the-shared-block"),
        pytest.param("bc974070a1b2", [], id="nothing-announced"),
        pytest.param("bc974070a1b2", [AirfiDiscoveredDevice(host="192.168.1.61", serial=1, model_id=1)], id="other-ip"),
    ],
)
async def test_device_seen_by_dhcp_that_is_no_airfi_unit_is_dropped(
    hass: HomeAssistant,
    macaddress: str,
    found: list[AirfiDiscoveredDevice],
) -> None:
    """A device whose seventh MAC digit is not Airfi's, or that announces nothing from its address, is not shown."""
    with _scan_finds(*found):
        result = await _dhcp_sees(hass, UNIT.host, macaddress)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_airfi_device"


@pytest.mark.integration
async def test_device_seen_by_dhcp_is_dropped_when_the_scan_cannot_start(hass: HomeAssistant) -> None:
    """When the scan cannot open its socket, the device is not shown."""
    with patch.object(AirfiDiscoveryService, "async_scan", AsyncMock(side_effect=OSError("address in use"))):
        result = await _dhcp_sees(hass, UNIT.host)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_airfi_device"


@pytest.mark.integration
async def test_unit_seen_by_dhcp_at_its_stored_address_needs_no_scan(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A device at the address of a unit already set up, as on every restart, is dropped without a scan."""
    with _scan_finds() as scan:
        result = await _dhcp_sees(hass, init_integration.data[CONF_HOST])

    scan.assert_not_awaited()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.integration
async def test_unit_seen_by_dhcp_at_a_new_address_is_followed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A unit already set up that DHCP sees at another address has the new address stored."""
    moved = AirfiDiscoveredDevice(host="192.168.1.77", serial=12345678, model_id=1)
    with _scan_finds(moved):
        result = await _dhcp_sees(hass, moved.host)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert init_integration.data[CONF_HOST] == moved.host


@pytest.mark.integration
async def test_unit_seen_by_dhcp_uses_what_the_listener_heard(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """When the running listener already heard the unit, the flow needs no scan of its own."""
    announce(UNIT.host, UNIT.serial, UNIT.model_id)
    await hass.async_block_till_done()

    with _scan_finds() as scan:
        result = await _dhcp_sees(hass, UNIT.host)

    scan.assert_not_awaited()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_manual_setup_is_not_blocked_by_an_open_discovery(hass: HomeAssistant) -> None:
    """A unit offered under Discovered can still be added by hand; the offer then disappears."""
    with _scan_finds(UNIT):
        await _dhcp_sees(hass, UNIT.host)

    with _scan_finds():
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
    with _connection_works():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: UNIT.host, CONF_SERIAL_NUMBER: "67890", CONF_MODEL_NAME: "Model 100 L"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
