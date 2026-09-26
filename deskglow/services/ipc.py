"""Local request/response IPC between the daemon and its clients.

Messages are JSON objects; the transport frames one message per line.
"""
from typing import Any, Protocol


class IpcHandler(Protocol):
    """What the server calls for each incoming connection's single request."""

    async def handle_request(self, request: Any) -> dict:
        """The reply for one decoded request (not necessarily a dict)."""

    def malformed(self, error: Exception) -> dict:
        """The reply for a request that could not be decoded."""


class IpcServer(Protocol):
    address: str  # human-readable endpoint, for logs

    def exists(self) -> bool:
        """True if something (live or stale) already occupies the endpoint."""

    def remove_stale(self) -> None:
        """Remove a stale endpoint left by a daemon that died."""

    async def start(self, handler: IpcHandler) -> None:
        """Start serving. The endpoint is private to the current user."""

    async def close(self) -> None:
        """Stop accepting connections."""

    def remove(self) -> None:
        """Remove the endpoint after shutdown. Never raises."""


class IpcClient(Protocol):
    async def request(self, message: Any, timeout: float = 25.0) -> Any | None:
        """Send one request and return the reply, or None if the peer hung up.

        Raises OSError (incl. FileNotFoundError) if nobody is listening,
        asyncio.TimeoutError if no reply comes, ValueError on a garbage reply."""
