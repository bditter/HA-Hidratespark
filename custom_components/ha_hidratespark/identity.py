"""Stable bottle identity helpers."""

from __future__ import annotations


def normalize_bottle_name(name: str | None) -> str | None:
    """Return the stable identity key for an advertised bottle name."""
    if name is None:
        return None
    normalized = name.strip().casefold()
    return normalized or None
