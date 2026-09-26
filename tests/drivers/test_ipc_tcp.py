"""drivers.ipc_tcp: loopback TCP + token file (the Windows IPC), on a REAL
127.0.0.1 socket. Runs on every OS."""
import asyncio
import json
import types

import pytest

from deskglow.drivers.ipc_framing import read_message, write_message
from deskglow.drivers.ipc_tcp import (TcpIpcClient, TcpIpcServer, default_endpoint_path,
                                      read_endpoint)


class Handler:
    def __init__(self):
        self.requests = []

    async def handle_request(self, request):
        self.requests.append(request)
        return {"ok": True, "got": request}

    def malformed(self, error):
        return {"ok": False, "error": "malformed"}


@pytest.fixture
async def served(tmp_path):
    path = str(tmp_path / "sub" / "deskglowd.json")
    server, handler = TcpIpcServer(path), Handler()
    await server.start(handler)
    yield server, handler, path
    await server.close()
    server.remove()


def test_endpoint_file_lives_in_the_local_app_data_dir(tmp_path):
    dirs = types.SimpleNamespace(user_data_dir=str(tmp_path))
    assert default_endpoint_path(dirs) == str(tmp_path / "deskglowd.json")


async def test_round_trip_through_the_client(served):
    server, handler, path = served
    assert await TcpIpcClient(path).request({"cmd": "ping"}, timeout=5) == {
        "ok": True, "got": {"cmd": "ping"}}
    assert handler.requests == [{"cmd": "ping"}]
    assert "127.0.0.1:" in server.address


async def test_endpoint_file_holds_the_port_and_a_fresh_256_bit_token(served, tmp_path):
    server, _h, path = served
    port, token = read_endpoint(path)
    assert port == server.port > 0
    assert len(token) == 64 and int(token, 16) >= 0
    other = TcpIpcServer(str(tmp_path / "other.json"))
    await other.start(Handler())
    try:
        assert read_endpoint(other.endpoint_file)[1] != token, "tokens must not repeat"
    finally:
        await other.close()


async def _raw(port, *lines):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        for line in lines:
            await write_message(writer, line)
        return await asyncio.wait_for(read_message(reader), 5)
    except ConnectionResetError:          # hung up with our 2nd line unread: RST
        return None
    finally:
        writer.close()


@pytest.mark.parametrize("first", ["0" * 64, "", None, {"cmd": "ping"}, 12345])
async def test_a_wrong_or_missing_token_is_hung_up_on_unheard(served, first):
    server, handler, _path = served
    reply = await _raw(server.port, first, {"cmd": "ping"})
    assert reply is None, "the server answered an unauthenticated peer"
    assert handler.requests == [], "the request reached the daemon"


async def test_garbage_after_a_valid_token_gets_the_malformed_reply(served):
    server, _h, _path = served
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    await write_message(writer, server.token)
    writer.write(b"{nope\n")
    await writer.drain()
    assert await asyncio.wait_for(read_message(reader), 5) == {
        "ok": False, "error": "malformed"}
    writer.close()


async def test_a_missing_endpoint_file_means_nobody_is_listening(tmp_path):
    with pytest.raises(FileNotFoundError):
        await TcpIpcClient(str(tmp_path / "none.json")).request({"cmd": "ping"})


@pytest.mark.parametrize("junk", ["", "{", '{"port": 1}', '["x"]'])
async def test_a_corrupt_endpoint_file_is_a_connection_error(tmp_path, junk):
    path = tmp_path / "e.json"
    path.write_text(junk)
    with pytest.raises(ConnectionRefusedError):
        await TcpIpcClient(str(path)).request({"cmd": "ping"})


async def test_a_stale_endpoint_file_refuses_like_a_dead_socket(tmp_path):
    """A file left by a killed daemon points at a closed port: OSError, so the
    daemon's startup treats it as stale and removes it."""
    path = str(tmp_path / "e.json")
    server = TcpIpcServer(path)
    await server.start(Handler())
    await server.close()
    assert server.exists()
    with pytest.raises(OSError):
        await TcpIpcClient(path).request({"cmd": "ping"}, timeout=2)
    server.remove_stale()
    assert not server.exists()
    server.remove()                       # already gone: never raises


async def test_the_endpoint_file_is_replaced_atomically(served, tmp_path):
    _server, _h, path = served
    assert sorted(p.name for p in (tmp_path / "sub").iterdir()) == ["deskglowd.json"]
    with open(path) as f:
        assert set(json.load(f)) == {"port", "token", "pid"}
