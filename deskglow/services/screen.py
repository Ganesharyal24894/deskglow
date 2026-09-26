"""Screen capture and focus tracking, as the screen mode needs them.

A rect is a dict with integer 'left', 'top', 'width' and 'height' (pixels in
the virtual-desktop coordinate space).
"""
from typing import Any, Protocol

Rect = dict[str, int]


class ScreenSource(Protocol):
    """Grabs pixels. Implementations own any thread affinity their backend
    needs (e.g. mss handles must stay on one thread), hence the async API."""

    async def monitors(self) -> dict[str, Rect]:
        """{name: rect} for every monitor; {} when no display is reachable."""

    async def grab(self, rect: Rect) -> Any:
        """An HxWx3 uint8 RGB array-like of the pixels inside `rect`."""

    def close(self) -> None:
        """Release the capture handle. Never raises."""


class FocusTracker(Protocol):
    def center(self) -> tuple[int, int] | None:
        """Centre of the focused window (else the pointer), or None if unknown."""

    def close(self) -> None:
        """Release the display connection. Never raises."""
