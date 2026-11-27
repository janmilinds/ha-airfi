"""Which Modbus registers each Airfi register map version provides."""

type MapVersion = tuple[int, int, int]

REGISTER_LENGTHS_BY_MAP_VERSION: tuple[tuple[MapVersion, tuple[int, int]], ...] = (
    ((3, 4, 0), (50, 68)),
    ((2, 9, 0), (47, 65)),
    ((2, 7, 0), (42, 59)),
    ((2, 5, 0), (40, 58)),
    ((2, 3, 0), (40, 55)),
    ((2, 1, 0), (40, 51)),
    ((2, 0, 0), (40, 34)),
)


def register_lengths(map_version: MapVersion) -> tuple[int, int]:
    """Return the input and holding register counts a unit on this register map answers.

    A version between two known maps gets the lengths of the nearest lower one: reading a
    register the unit lacks fails the whole read, so the lengths are never guessed upwards.
    A version below the oldest known map gets the oldest map's lengths.
    """
    for min_version, lengths in REGISTER_LENGTHS_BY_MAP_VERSION:
        if map_version >= min_version:
            return lengths
    return REGISTER_LENGTHS_BY_MAP_VERSION[-1][1]


__all__ = ["REGISTER_LENGTHS_BY_MAP_VERSION", "MapVersion", "register_lengths"]
