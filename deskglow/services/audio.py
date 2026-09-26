"""Audio capture for the audio-reactive mode."""
from collections.abc import Sequence
from typing import Protocol


class AudioSource(Protocol):
    async def start(self, source: str, target: str | None, rate: int, block: int) -> str:
        """Start capturing mono audio.

        source is "system" (what the speakers play) or "mic" (default input);
        an explicit backend-specific `target` wins over both. Returns a short
        human description of what is being captured, for the log."""

    async def read(self) -> Sequence[float] | None:
        """The next `block` samples as floats in -1..1, or None at end of stream."""

    async def stop(self) -> None:
        """Stop capturing and release the device. Safe to call more than once."""
