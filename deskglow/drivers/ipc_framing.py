"""Newline-delimited JSON framing over asyncio streams."""
import json

_NEWLINE = b"\n"
_CHUNK = 65536


async def read_message(reader):
    """Read one newline-terminated JSON message, or None at end of stream.

    Deliberately not reader.readline(): asyncio caps a single line at 64 KiB and
    raises rather than returning it, which would make any larger request
    unreadable. Bytes past the newline are kept for the next call, so this stays
    correct if a peer ever pipelines messages.

    A stream that ends without a newline is a closed connection, not a message,
    so it reads as None like any other EOF. Garbage raises ValueError.
    """
    buf = bytearray(getattr(reader, "_deskglow_leftover", b""))
    while _NEWLINE not in buf:
        chunk = await reader.read(_CHUNK)
        if not chunk:                      # EOF: partial line is not a message
            reader._deskglow_leftover = b""
            return None
        buf += chunk
    line, _, rest = bytes(buf).partition(_NEWLINE)
    reader._deskglow_leftover = rest
    return json.loads(line.decode())


async def write_message(writer, obj):
    """Write one message as a single line (json.dumps never emits a raw newline)."""
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()
