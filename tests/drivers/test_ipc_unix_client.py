"""UnixIpcClient against a REAL unix domain socket created in tmp_path."""
import asyncio
import sys

import pytest

from deskglow.drivers.ipc_framing import read_message, write_message
from deskglow.drivers.ipc_unix import UnixIpcClient

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="AF_UNIX asyncio sockets are POSIX-only; "
                                       "Windows uses ipc_tcp (tests/drivers/test_ipc_tcp*.py)")


@pytest.fixture
async def serve(tmp_path):
    """Start a raw unix-socket server in tmp_path; return (path, handler errors)."""
    started = []

    async def _serve(handler, name="deskglowd.sock"):
        path = str(tmp_path / name)
        errors = []

        async def wrapper(reader, writer):
            try:
                await handler(reader, writer)
            except Exception as exc:      # noqa: BLE001 - recorded, then asserted on
                errors.append(exc)
            finally:
                writer.close()

        server = await asyncio.start_unix_server(wrapper, path)
        started.append(server)
        return path, errors

    yield _serve

    for server in started:
        server.close()
        await server.wait_closed()


async def echo_handler(reader, writer):
    """Reply with whatever was sent, wrapped so the shape is unambiguous."""
    msg = await read_message(reader)
    await write_message(writer, {"echo": msg})


def request(path, payload, timeout=5.0):
    return UnixIpcClient(path).request(payload, timeout=timeout)


@pytest.mark.parametrize("payload", [
    {"cmd": "status"},
    {"desc": "pomodoro — 25′ ✓ café ☕ 日本語 🎨", "emoji": "🌈"},
    {"args": {"rgb": [0, 0, 0], "on": False, "n": 0, "x": None, "l": []}},
    {"blob": "x" * 200_000},
], ids=["simple", "unicode", "falsy-values", "large"])
async def test_request_round_trips_over_a_real_unix_socket(serve, payload):
    """One request in, one JSON reply out: nothing lost, no size limit."""
    path, errors = await serve(echo_handler)
    assert await request(path, payload) == {"echo": payload}
    assert errors == []


async def test_request_returns_none_when_the_server_closes_without_replying(serve):
    """The CLI turns this into 'no response from daemon'."""

    async def hang_up(reader, writer):
        await read_message(reader)

    path, errors = await serve(hang_up)
    assert await request(path, {"cmd": "ping"}) is None
    assert errors == []


async def test_request_reports_a_garbage_reply_as_a_clean_error(serve):
    """A daemon that answers with junk raises a ValueError the caller can report."""

    async def garbage(reader, writer):
        await read_message(reader)
        writer.write(b"<html>500</html>\n")
        await writer.drain()

    path, errors = await serve(garbage)
    with pytest.raises(ValueError):
        await request(path, {"cmd": "ping"})
    assert errors == []


async def test_request_times_out_when_the_server_never_replies(serve):
    """A wedged daemon must not hang the CLI forever."""

    async def never_replies(reader, writer):
        await read_message(reader)
        await reader.read()          # sit here until the client gives up

    path, errors = await serve(never_replies)
    with pytest.raises(asyncio.TimeoutError):
        await request(path, {"cmd": "status"}, timeout=0.05)
    assert errors == []


async def test_request_raises_when_the_socket_path_does_not_exist(tmp_path):
    """No daemon running => a plain FileNotFoundError ('not running')."""
    with pytest.raises(FileNotFoundError):
        await request(str(tmp_path / "nope.sock"), {"cmd": "ping"}, timeout=1.0)


async def test_request_raises_when_the_path_is_not_a_socket(tmp_path):
    """A stale regular file at the socket path is an OSError, not a hang."""
    bogus = tmp_path / "not-a-socket"
    bogus.write_text("stale")
    with pytest.raises(OSError):
        await request(str(bogus), {"cmd": "ping"}, timeout=1.0)


async def _closes_after(serve, reply_with, timeout, expect):
    """Assert the server sees EOF once request() has returned or raised."""
    saw_eof = asyncio.Event()

    async def handler(reader, writer):
        await read_message(reader)
        if reply_with is not None:
            writer.write(reply_with)
            await writer.drain()
        assert await reader.read() == b"", "client did not close its end"
        saw_eof.set()

    path, errors = await serve(handler)
    if expect is None:
        assert await request(path, {"cmd": "ping"}, timeout=timeout) == {"ok": True}
    else:
        with pytest.raises(expect):
            await request(path, {"cmd": "ping"}, timeout=timeout)
    await asyncio.wait_for(saw_eof.wait(), timeout=5.0)
    assert errors == []


async def test_request_closes_the_connection_it_opened(serve):
    """Leaking a socket per command would exhaust the daemon's descriptors."""
    await _closes_after(serve, b'{"ok": true}\n', 5.0, None)


async def test_request_closes_the_connection_even_when_it_times_out(serve):
    """The timeout path is the one that would leak, so it gets its own test."""
    await _closes_after(serve, None, 0.05, asyncio.TimeoutError)


async def test_request_closes_the_connection_when_the_reply_is_garbage(serve):
    """An error reading the reply must still release the socket."""
    await _closes_after(serve, b"nonsense\n", 5.0, ValueError)


async def test_repeated_requests_reuse_nothing_and_all_succeed(serve):
    """Each command is an independent connection; ten in a row all work."""
    path, errors = await serve(echo_handler)
    for i in range(10):
        assert await request(path, {"n": i}) == {"echo": {"n": i}}
    assert errors == []
