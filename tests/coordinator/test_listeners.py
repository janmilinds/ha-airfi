"""Test coordinator listener utilities for Airfi."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from custom_components.airfi.coordinator.listeners import (
    create_entity_callback,
    should_notify_entity,
    track_update_performance,
)


@pytest.mark.unit
async def test_create_entity_callback_calls_inner() -> None:
    """Test that wrapped callback calls the original function."""
    inner = AsyncMock()
    wrapped = create_entity_callback("sensor.test", inner)

    await wrapped()

    inner.assert_awaited_once()


@pytest.mark.unit
async def test_create_entity_callback_catches_exceptions(caplog) -> None:
    """Test that errors in inner callback are caught and logged."""
    inner = AsyncMock(side_effect=RuntimeError("boom"))
    wrapped = create_entity_callback("sensor.test", inner)

    with caplog.at_level(logging.ERROR, logger="custom_components.airfi"):
        await wrapped()

    assert "sensor.test" in caplog.text


@pytest.mark.unit
def test_should_notify_entity_returns_false_for_unchanged() -> None:
    """Test that notification is skipped when entity value is unchanged."""
    old = {"temperature": 20.0, "humidity": 50}
    new = {"temperature": 20.1, "humidity": 50}

    assert should_notify_entity(old, new, "humidity") is False


@pytest.mark.unit
def test_should_notify_entity_returns_true_for_changed() -> None:
    """Test that notification triggers when value changes."""
    old = {"temperature": 20.0}
    new = {"temperature": 21.0}

    assert should_notify_entity(old, new, "temperature") is True


@pytest.mark.unit
def test_should_notify_entity_returns_true_when_new_key() -> None:
    """Test that notification triggers when a new key appears."""
    old: dict = {}
    new = {"temperature": 20.0}

    assert should_notify_entity(old, new, "temperature") is True


@pytest.mark.unit
def test_should_notify_entity_returns_true_when_key_removed() -> None:
    """Test that notification triggers when a key is removed."""
    old = {"temperature": 20.0}
    new: dict = {}

    assert should_notify_entity(old, new, "temperature") is True


@pytest.mark.unit
def test_should_notify_entity_returns_false_for_missing_key() -> None:
    """Test that notification is skipped when key doesn't exist in either."""
    old = {"temperature": 20.0}
    new = {"temperature": 20.0}

    assert should_notify_entity(old, new, "humidity") is False


@pytest.mark.unit
def test_track_update_performance_debug(caplog) -> None:
    """Test that fast updates are logged at debug level."""
    with caplog.at_level(logging.DEBUG, logger="custom_components.airfi"):
        track_update_performance(0.5)

    assert "0.50 seconds" in caplog.text


@pytest.mark.unit
def test_track_update_performance_slow(caplog) -> None:
    """Test that slow updates are logged at info level."""
    with caplog.at_level(logging.INFO, logger="custom_components.airfi"):
        track_update_performance(6.0)

    assert "slow" in caplog.text.lower()


@pytest.mark.unit
def test_track_update_performance_very_slow(caplog) -> None:
    """Test that very slow updates are logged at warning level."""
    with caplog.at_level(logging.WARNING, logger="custom_components.airfi"):
        track_update_performance(11.0)

    assert "very slow" in caplog.text.lower()
