"""Tests for Airfi UDP discovery."""

from __future__ import annotations

import asyncio
import socket
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice, AirfiDiscoveryService, get_model_name

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
def test_get_model_name_negative_wraps_around() -> None:
    """Test that model_id=0 wraps via negative index in Python."""
    # (0-1)//2 = -1 → accesses last model entry (Python negative indexing)
    result = get_model_name(0)
    assert "Model" in result


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
# _parse_packet
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_packet_uses_ip_from_payload() -> None:
    """Test that device IP is parsed from payload instead of UDP sender IP."""
    service = AirfiDiscoveryService()

    packet = bytes.fromhex("f714650aa00f21a498000102000000")

    device = service._parse_packet(packet, "172.17.0.2")  # noqa: SLF001

    assert device is not None
    assert device.host == "10.101.20.247"
    assert device.serial == 10003489
    assert device.model_id == 2


@pytest.mark.unit
def test_parse_packet_falls_back_to_sender_ip_when_payload_ip_is_zero() -> None:
    """Test that sender IP is used only when payload IP is unset."""
    service = AirfiDiscoveryService()

    packet = bytes.fromhex("00000000a00f21a498000102000000")

    device = service._parse_packet(packet, "172.17.0.2")  # noqa: SLF001

    assert device is not None
    assert device.host == "172.17.0.2"


@pytest.mark.unit
def test_parse_packet_short_packet_returns_none() -> None:
    """Test that packets shorter than 12 bytes are rejected."""
    service = AirfiDiscoveryService()
    assert service._parse_packet(b"\x00" * 11, "1.2.3.4") is None  # noqa: SLF001


@pytest.mark.unit
def test_parse_packet_wrong_port_returns_none() -> None:
    """Test that packets with non-4000 port field are rejected."""
    service = AirfiDiscoveryService()
    # Build a 12-byte packet with port = 5000 (0x1388) at bytes 4-5
    ip_bytes = b"\xc0\xa8\x01\x0a"  # 192.168.1.10 reversed
    port_bytes = struct.pack("<H", 5000)
    rest = b"\x00" * 6
    packet = ip_bytes + port_bytes + rest
    assert service._parse_packet(packet, "1.2.3.4") is None  # noqa: SLF001


@pytest.mark.unit
def test_parse_packet_struct_error_returns_none() -> None:
    """Test that malformed packet data returns None on struct error."""
    service = AirfiDiscoveryService()
    with patch("custom_components.airfi.utils.discovery.struct.unpack_from", side_effect=struct.error("bad")):
        assert service._parse_packet(b"\x00" * 12, "1.2.3.4") is None  # noqa: SLF001


@pytest.mark.unit
def test_parse_packet_model_id_zero_returns_none() -> None:
    """Test that model_id=0 is rejected as invalid."""
    service = AirfiDiscoveryService()
    # Build a 12-byte packet: valid IP, port=4000, serial=1, unknown=0, model_id=0
    ip_bytes = b"\x0a\x01\xa8\xc0"  # 192.168.1.10 reversed
    port_bytes = struct.pack("<H", 4000)
    serial_bytes = struct.pack("<I", 1)
    unknown_model = b"\x00\x00"  # byte 10=0, byte 11=0 (model_id=0)
    packet = ip_bytes + port_bytes + serial_bytes + unknown_model
    assert service._parse_packet(packet, "1.2.3.4") is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# _create_socket
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_socket_returns_socket() -> None:
    """Test that _create_socket creates and configures a UDP socket."""
    service = AirfiDiscoveryService()
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        result = service._create_socket()  # noqa: SLF001

    assert result is mock_sock
    mock_socket_cls.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    mock_sock.bind.assert_called_once()
    mock_sock.setblocking.assert_called_once_with(False)


# ---------------------------------------------------------------------------
# async_scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_scan_socket_creation_failure() -> None:
    """Test that async_scan returns empty list when socket creation fails."""
    service = AirfiDiscoveryService()

    with patch.object(service, "_create_socket", side_effect=OSError("bind failed")):
        result = await service.async_scan(timeout_seconds=1)

    assert result == []


@pytest.mark.unit
async def test_async_scan_timeout_with_no_devices() -> None:
    """Test that scan returns empty list after timeout with no packets."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()

    with (
        patch.object(service, "_create_socket", return_value=mock_sock),
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
    packet = bytes.fromhex("f714650aa00f21a498000102000000")

    call_count = 0

    async def _fake_receive():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (packet, ("172.17.0.2", 12345))
        raise TimeoutError

    with (
        patch.object(service, "_create_socket", return_value=mock_sock),
        patch.object(service, "_async_receive", side_effect=_fake_receive),
    ):
        result = await service.async_scan(timeout_seconds=0.3, quiet_period_seconds=0.1)

    assert len(result) == 1
    assert result[0].host == "10.101.20.247"
    assert result[0].serial == 10003489


@pytest.mark.unit
async def test_async_scan_deduplicates_same_device() -> None:
    """Test that scan deduplicates by unique_key (serial)."""
    service = AirfiDiscoveryService()
    mock_sock = MagicMock()
    packet = bytes.fromhex("f714650aa00f21a498000102000000")

    call_count = 0

    async def _fake_receive():
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            return (packet, ("172.17.0.2", 12345))
        raise TimeoutError

    with (
        patch.object(service, "_create_socket", return_value=mock_sock),
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
        patch.object(service, "_create_socket", return_value=mock_sock),
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
    loop = asyncio.get_event_loop()

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
