"""Where on Earth the user roughly is, for sunset-based schedules.

No GPS or network lookups: implementations derive an approximate position from
the configured time zone (e.g. the tz database's zone coordinates).
"""
from __future__ import annotations

from typing import Protocol


class LocationHint(Protocol):
    def __call__(self) -> tuple[float, float] | None:
        """(latitude, longitude) in degrees, or None if unknown."""


def no_location() -> tuple[float, float] | None:
    """Fallback LocationHint: position unknown."""
    return None
