"""Tests for Airfi UDP discovery packet parsing."""

from __future__ import annotations

import pytest

from custom_components.airfi.utils.discovery import AirfiDiscoveryService


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
