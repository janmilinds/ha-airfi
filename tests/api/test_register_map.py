"""Test which registers each register map version provides."""

import pytest

from custom_components.airfi_home.api.register_map import MapVersion, register_lengths


@pytest.mark.unit
@pytest.mark.parametrize(
    ("map_version", "expected"),
    [
        ((2, 7, 0), (42, 59)),
        ((2, 5, 0), (40, 58)),
        ((2, 3, 0), (40, 55)),
        ((2, 1, 0), (40, 51)),
        ((2, 0, 0), (40, 34)),
    ],
)
def test_register_lengths_by_version(map_version: MapVersion, expected: tuple[int, int]) -> None:
    """Each known register map version reads its own lengths."""
    assert register_lengths(map_version) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("map_version", "expected"),
    [
        ((2, 6, 0), (40, 58)),
    ],
)
def test_register_lengths_between_known_versions_take_the_lower_one(
    map_version: MapVersion, expected: tuple[int, int]
) -> None:
    """A version the table does not list gets the nearest lower known version's lengths."""
    assert register_lengths(map_version) == expected


@pytest.mark.unit
def test_register_lengths_fallback_for_older_version() -> None:
    """An older version than the table knows falls back to the oldest mapping."""
    assert register_lengths((1, 5, 0)) == (40, 34)
