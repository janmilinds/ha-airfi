"""Tests for Airfi UDP discovery."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import socket
import struct
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.airfi.const import (
    DISCOVERY_LISTENER_RETRY_SECONDS,
    DISCOVERY_MULTICAST_GROUP,
    DISCOVERY_MULTICAST_PORT,
    DOMAIN,
)
from custom_components.airfi.utils.discovery import (
    AirfiDiscoveredDevice,
    AirfiDiscoveryService,
    announced_device_at,
    create_discovery_socket,
    get_model_name,
    parse_announcement,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_INTEGRATION_DISCOVERY, ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

# ---------------------------------------------------------------------------
# get_model_name
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        (1, "Model 60 L"),
        (2, "Model 60 R"),
        (3, "Model 100 L"),
        (4, "Model 100 R"),
        (5, "Model 150 L"),
    ],
)
def test_get_model_name_valid(model_id: int, expected: str) -> None:
    """Test model name lookup for known IDs."""
    assert get_model_name(model_id) == expected


@pytest.mark.unit
def test_get_model_name_unknown_returns_unknown() -> None:
    """Test that out-of-range model ID returns 'Unknown'."""
    assert get_model_name(255) == "Unknown"


@pytest.mark.unit
def test_get_model_name_zero_returns_unknown() -> None:
    """Test that model_id=0 returns 'Unknown' (invalid; rejected by parse_announcement)."""
    assert get_model_name(0) == "Unknown"


# ---------------------------------------------------------------------------
# AirfiDiscoveredDevice properties
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_discovered_device_model_name() -> None:
    """Test model_name property delegates to get_model_name."""
    device = AirfiDiscoveredDevice(host="192.168.1.10", serial=12345, model_id=2)
    assert device.model_name == "Model 60 R"


@pytest.mark.unit
def test_discovered_device_unique_key() -> None:
    """Test unique_key returns string serial."""
    device = AirfiDiscoveredDevice(host="192.168.1.10", serial=12345, model_id=1)
    assert device.unique_key == "12345"


# ---------------------------------------------------------------------------
# parse_announcement
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_packet_uses_ip_from_payload() -> None:
    """Test that device IP is parsed from payload instead of UDP sender IP."""
    packet = bytes.fromhex("0a0200c0a00f4e61bc000102000000")

    device = parse_announcement(packet, "172.17.0.2")

    assert device is not None
    assert device.host == "192.0.2.10"
    assert device.serial == 12345678
    assert device.model_id == 2


@pytest.mark.unit
def test_parse_packet_falls_back_to_sender_ip_when_payload_ip_is_zero() -> None:
    """Test that sender IP is used only when payload IP is unset."""
    packet = bytes.fromhex("00000000a00f4e61bc000102000000")

    device = parse_announcement(packet, "172.17.0.2")

    assert device is not None
    assert device.host == "172.17.0.2"


@pytest.mark.unit
def test_parse_packet_short_packet_returns_none() -> None:
    """Test that packets shorter than 12 bytes are rejected."""
    assert parse_announcement(b"\x00" * 11, "1.2.3.4") is None


@pytest.mark.unit
def test_parse_packet_wrong_port_returns_none() -> None:
    """Test that packets with non-4000 port field are rejected."""
    # Build a 12-byte packet with port = 5000 (0x1388) at bytes 4-5
    ip_bytes = b"\xc0\xa8\x01\x0a"  # 192.168.1.10 reversed
    port_bytes = struct.pack("<H", 5000)
    rest = b"\x00" * 6
    packet = ip_bytes + port_bytes + rest
    assert parse_announcement(packet, "1.2.3.4") is None


@pytest.mark.unit
def test_parse_packet_struct_error_returns_none() -> None:
    """Test that malformed packet data returns None on struct error."""
    with patch("custom_components.airfi.utils.discovery.struct.unpack_from", side_effect=struct.error("bad")):
        assert parse_announcement(b"\x00" * 12, "1.2.3.4") is None


@pytest.mark.unit
def test_parse_packet_model_id_zero_returns_none() -> None:
    """Test that model_id=0 is rejected as invalid."""
    # Build a 12-byte packet: valid IP, port=4000, serial=1, unknown=0, model_id=0
    ip_bytes = b"\x0a\x01\xa8\xc0"  # 192.168.1.10 reversed
    port_bytes = struct.pack("<H", 4000)
    serial_bytes = struct.pack("<I", 1)
    unknown_model = b"\x00\x00"  # byte 10=0, byte 11=0 (model_id=0)
    packet = ip_bytes + port_bytes + serial_bytes + unknown_model
    assert parse_announcement(packet, "1.2.3.4") is None


# ---------------------------------------------------------------------------
# create_discovery_socket
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_socket_returns_socket() -> None:
    """Test that create_discovery_socket creates and configures a UDP socket."""
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        result = create_discovery_socket()

    assert result is mock_sock
    mock_socket_cls.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    mock_sock.bind.assert_called_once_with((DISCOVERY_MULTICAST_GROUP, DISCOVERY_MULTICAST_PORT))
    mock_sock.setblocking.assert_called_once_with(False)


@pytest.mark.unit
def test_create_socket_closes_socket_when_bind_fails() -> None:
    """Test that create_discovery_socket closes the socket when configuring it fails."""
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = OSError("address in use")
        mock_socket_cls.return_value = mock_sock

        with pytest.raises(OSError, match="address in use"):
            create_discovery_socket()

    mock_sock.close.assert_called_once()


# ---------------------------------------------------------------------------
# async_scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_scan_socket_creation_failure() -> None:
    """Test that async_scan raises OSError when socket creation fails."""
    service = AirfiDiscoveryService()

    with (
        patch("custom_components.airfi.utils.discovery.create_discovery_socket", side_effect=OSError("bind failed")),
        pytest.raises(OSError, match="bind failed"),
    ):
        await service.async_scan(timeout_seconds=1)


@pytest.mark.unit
async def test_async_scan_timeout_with_no_devices() -> None:
    """Test that scan returns empty list after timeout with no packets."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()

    with (
        patch("custom_components.airfi.utils.discovery.create_discovery_socket", return_value=mock_sock),
        patch.object(service, "_async_receive", new=AsyncMock(side_effect=TimeoutError)),
    ):
        result = await service.async_scan(timeout_seconds=0.1, quiet_period_seconds=0.05)

    assert result == []
    mock_sock.close.assert_called_once()


@pytest.mark.unit
async def test_async_scan_finds_device() -> None:
    """Test that scan returns a device when a valid packet is received."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()
    packet = bytes.fromhex("0a0200c0a00f4e61bc000102000000")

    call_count = 0

    async def _fake_receive():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (packet, ("172.17.0.2", 12345))
        raise TimeoutError

    with (
        patch("custom_components.airfi.utils.discovery.create_discovery_socket", return_value=mock_sock),
        patch.object(service, "_async_receive", side_effect=_fake_receive),
    ):
        result = await service.async_scan(timeout_seconds=0.3, quiet_period_seconds=0.1)

    assert len(result) == 1
    assert result[0].host == "192.0.2.10"
    assert result[0].serial == 12345678


@pytest.mark.unit
async def test_async_scan_deduplicates_same_device() -> None:
    """Test that scan deduplicates by unique_key (serial)."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()
    packet = bytes.fromhex("0a0200c0a00f4e61bc000102000000")

    call_count = 0

    async def _fake_receive():
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return (packet, ("172.17.0.2", 12345))
        raise TimeoutError

    with (
        patch("custom_components.airfi.utils.discovery.create_discovery_socket", return_value=mock_sock),
        patch.object(service, "_async_receive", side_effect=_fake_receive),
    ):
        result = await service.async_scan(timeout_seconds=0.3, quiet_period_seconds=0.1)

    assert len(result) == 1


@pytest.mark.unit
async def test_async_scan_generic_error() -> None:
    """Test that generic exceptions in scan loop are caught and logged."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()

    with (
        patch("custom_components.airfi.utils.discovery.create_discovery_socket", return_value=mock_sock),
        patch.object(service, "_async_receive", new=AsyncMock(side_effect=RuntimeError("boom"))),
    ):
        result = await service.async_scan(timeout_seconds=0.1)

    assert result == []
    mock_sock.close.assert_called_once()


# ---------------------------------------------------------------------------
# _async_receive
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_receive_delegates_to_loop() -> None:
    """Test that _async_receive delegates to event loop."""
    service = AirfiDiscoveryService()
    service.sock = MagicMock()

    expected = (b"data", ("1.2.3.4", 5000))
    loop = asyncio.get_running_loop()

    with patch.object(loop, "sock_recvfrom", new=AsyncMock(return_value=expected)):
        result = await service._async_receive()  # noqa: SLF001

    assert result == expected


# ---------------------------------------------------------------------------
# get_discovered_devices
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_discovered_devices_returns_list() -> None:
    """Test that get_discovered_devices returns stored devices."""
    service = AirfiDiscoveryService()
    device = AirfiDiscoveredDevice(host="192.168.1.10", serial=12345, model_id=1)
    service.discovered = {"12345": device}

    result = service.get_discovered_devices()
    assert result == [device]


# ---------------------------------------------------------------------------
# AirfiDiscoveryListener
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_unit_announced_while_running_is_offered(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A unit that is not set up yet and announces itself is offered under Discovered, once."""
    announce("192.168.1.60", 67890, 3)
    announce("192.168.1.60", 67890, 3)
    await hass.async_block_till_done()

    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    assert flow["context"]["title_placeholders"] == {"name": "Airfi Model 100 L"}
    assert flow["step_id"] == "discovery_confirm"


@pytest.mark.integration
async def test_unit_announced_from_a_new_address_is_followed(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A unit already set up that announces itself from another address has the new address stored."""
    announce("192.168.1.77", 12345678)
    await hass.async_block_till_done()

    assert init_integration.data[CONF_HOST] == "192.168.1.77"
    assert init_integration.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.integration
async def test_unit_set_up_at_the_address_it_announces_opens_no_flow(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A unit already set up that announces itself from its stored address, as after every restart, starts nothing."""
    with patch("custom_components.airfi.discovery_flow.async_create_flow") as create_flow:
        announce(init_integration.data[CONF_HOST], 12345678)

    create_flow.assert_not_called()


@pytest.mark.integration
async def test_unit_that_moved_is_no_longer_heard_at_its_old_address(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """Once a unit announces itself from a new address, the listener no longer places it at the old one."""
    announce("192.168.1.60", 67890, 3)
    announce("192.168.1.61", 67890, 3)

    assert announced_device_at(hass, "192.168.1.60") is None
    assert announced_device_at(hass, "192.168.1.61") == AirfiDiscoveredDevice(
        host="192.168.1.61", serial=67890, model_id=3
    )


@pytest.mark.integration
async def test_unit_is_offered_again_once_its_entry_is_removed(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """After its entry is deleted, a unit the listener already knew is offered again at its next announcement."""
    announce(init_integration.data[CONF_HOST], 12345678)
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    announce(init_integration.data[CONF_HOST], 12345678)
    await hass.async_block_till_done()

    (flow,) = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["unique_id"] == "12345678"


@pytest.mark.integration
async def test_ignored_unit_is_not_offered_again(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A unit the user chose to ignore stays ignored when it announces itself."""
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id="67890").add_to_hass(hass)

    announce("192.168.1.60", 67890, 3)
    await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


@pytest.mark.integration
async def test_packet_that_is_no_announcement_is_ignored(
    hass: HomeAssistant,
    announce: Callable[..., None],
    init_integration: MockConfigEntry,
) -> None:
    """A datagram that does not parse as an announcement, here one with no model, opens nothing."""
    announce("192.168.1.60", 67890, 0)
    await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def _set_up(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add the entry and set it up."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _a_minute_passes(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the listener's retry delay pass."""
    freezer.tick(timedelta(seconds=DISCOVERY_LISTENER_RETRY_SECONDS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_listener_closes_its_socket_when_home_assistant_stops(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    discovery_socket: MagicMock,
) -> None:
    """Once Home Assistant stops, the listener leaves the network."""
    opened: list[socket.socket] = []
    open_socket = discovery_socket.side_effect

    def _open_and_keep() -> socket.socket:
        opened.append(sock := open_socket())
        return sock

    discovery_socket.side_effect = _open_and_keep
    await _set_up(hass, config_entry)
    (listener_socket,) = opened
    assert listener_socket.fileno() != -1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert listener_socket.fileno() == -1


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_listener_retries_until_the_network_is_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    discovery_socket: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """When the socket cannot be opened at startup, the listener tries again a minute later."""
    open_socket = discovery_socket.side_effect
    discovery_socket.side_effect = [OSError("network is unreachable"), open_socket()]
    await _set_up(hass, config_entry)
    assert discovery_socket.call_count == 1

    await _a_minute_passes(hass, freezer)

    assert discovery_socket.call_count == 2


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_stopping_cancels_a_pending_retry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    discovery_socket: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A retry still waiting when Home Assistant stops never runs."""
    discovery_socket.side_effect = OSError("network is unreachable")
    await _set_up(hass, config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await _a_minute_passes(hass, freezer)

    assert discovery_socket.call_count == 1
