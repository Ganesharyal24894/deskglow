"""System-wide keyboard shortcuts (used by the desktop app, not the daemon)."""
from typing import Protocol
from collections.abc import Callable


class GlobalHotkey(Protocol):
    def register(self, sequence: str, callback: Callable[[], None]) -> bool:
        """Call `callback` whenever `sequence` (e.g. "<ctrl>+<alt>+l") is
        pressed anywhere. False if this desktop can't grab global keys (for
        example a Wayland session). The callback may run on any thread."""

    def unregister(self) -> None:
        """Release the shortcut. Safe to call when nothing is registered."""
