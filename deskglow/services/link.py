"""The radio: open a connection to one strip, find it by address, fix bonds."""
from typing import Any, Protocol


class AdapterError(RuntimeError):
    """The Bluetooth adapter could not be reset; the message says why/what to do."""


class LinkSession(Protocol):
    """One connection attempt to one strip (a fresh object per attempt)."""

    @property
    def is_connected(self) -> bool: ...

    async def connect(self) -> None:
        """Connect, or raise. The caller disconnects a session whose connect raised."""

    async def write(self, frame: bytes, response: bool = False) -> None:
        """Write one whole frame to the preset's write characteristic.

        response=True asks for an acknowledged write, which fails on a dead link."""

    async def disconnect(self) -> None: ...


class LightLink(Protocol):
    """Factory and housekeeping for connections to strips on this machine."""

    def session(self, target: Any, timeout: float) -> LinkSession:
        """A new, unconnected session. `target` is an address string or a handle
        previously returned by find()."""

    async def find(self, address: str, timeout: float) -> Any | None:
        """Scan briefly for `address`; return a connectable handle or None.
        Must stop scanning before returning (other BT devices share the radio)."""

    def drop_bond(self, address: str) -> None:
        """Forget a stale pairing/bond for `address`. Never raises."""

    def reset_adapter(self, address: str | None) -> None:
        """Power-cycle the adapter and forget `address`'s bond (if given).
        Raises AdapterError with a human-readable message on failure."""
