"""Helpers for the unix IPC driver tests: in-memory streams and a raw server."""
import asyncio


def stream_of(data: bytes):
    """A StreamReader pre-loaded with `data` and then closed."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


class FakeWriter:
    """Captures the bytes write_message() puts on the wire."""

    def __init__(self):
        self.buf = bytearray()
        self.drains = 0
        self.closed = False

    def write(self, data):
        self.buf += data

    async def drain(self):
        self.drains += 1

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None
