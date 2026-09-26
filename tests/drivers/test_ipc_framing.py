"""Newline-delimited JSON framing (deskglow.drivers.ipc_framing), in memory."""
import json

import pytest
from ipc_support import FakeWriter, stream_of

from deskglow.drivers.ipc_framing import read_message, write_message


async def test_write_message_emits_one_json_line_and_flushes():
    """The wire format is exactly one JSON document per newline-terminated line."""
    writer = FakeWriter()
    await write_message(writer, {"cmd": "ping"})
    assert bytes(writer.buf) == b'{"cmd": "ping"}\n'
    assert writer.drains == 1


async def test_write_message_never_emits_an_embedded_newline():
    """A payload containing a newline must not be split into two messages."""
    writer = FakeWriter()
    await write_message(writer, {"err": "line one\nline two"})
    assert bytes(writer.buf).count(b"\n") == 1
    assert json.loads(bytes(writer.buf)) == {"err": "line one\nline two"}


async def test_read_message_reads_one_message_per_line():
    """Two queued messages are read back one at a time, in order."""
    reader = stream_of(b'{"a": 1}\n{"b": 2}\n')
    assert await read_message(reader) == {"a": 1}
    assert await read_message(reader) == {"b": 2}
    assert await read_message(reader) is None


async def test_write_then_read_round_trips_through_the_wire_format():
    """write_message and read_message agree on the framing."""
    writer = FakeWriter()
    await write_message(writer, {"ok": True, "modes": ["solid", "calm"]})
    assert await read_message(stream_of(bytes(writer.buf))) == {
        "ok": True, "modes": ["solid", "calm"]}


async def test_read_message_handles_a_line_longer_than_asyncios_limit():
    """asyncio's readline() caps a line at 64 KiB; the framing must not."""
    payload = {"blob": "y" * 300_000}
    writer = FakeWriter()
    await write_message(writer, payload)
    assert await read_message(stream_of(bytes(writer.buf))) == payload


async def test_read_message_returns_none_at_eof():
    """A peer that closed without sending anything reads as None, not an error."""
    assert await read_message(stream_of(b"")) is None


async def test_read_message_returns_none_on_a_truncated_line():
    """A peer killed part-way through a write (Ctrl-C on the CLI) leaves a line
    with no terminating newline. That is a closed connection, not a message, so
    it must read as None like any other EOF."""
    assert await read_message(stream_of(b'{"cmd": "sta')) is None


async def test_read_message_reports_garbage_as_a_clean_catchable_error():
    """Garbage on the socket surfaces as a ValueError (json.JSONDecodeError is
    one), so a caller can catch it without catching everything."""
    with pytest.raises(ValueError):
        await read_message(stream_of(b"this is not json\n"))


async def test_read_message_rejects_garbage_without_consuming_the_next_message():
    """Recovering from one bad line must still be possible: the reader is not
    left desynchronised part-way through the stream."""
    reader = stream_of(b"not json\n{\"ok\": true}\n")
    with pytest.raises(ValueError):
        await read_message(reader)
    assert await read_message(reader) == {"ok": True}
