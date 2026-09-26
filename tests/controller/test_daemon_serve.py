"""Daemon.serve(): socket bootstrap, restore, single-instance, malformed input.

Uses this OS's REAL IPC driver (unix socket, or loopback TCP on Windows) with
its endpoint inside tmp_path.
"""
import asyncio
import json
import os

import pytest
from daemon_support import (ENDPOINT_NAME, ipc_drivers, make_daemon, open_raw,
                            serve_in_background, shutdown_served)
from fakes import FakeStorage

from deskglow.controller import lifecycle


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


@pytest.fixture
def sock(tmp_path):
    return tmp_path / ENDPOINT_NAME


async def test_serve_creates_socket_answers_ping_and_cleans_up(sock):
    """serve() owns the socket for its whole life and removes it on shutdown."""
    d = make_daemon(sock)
    task, path = await serve_in_background(d)
    try:
        assert os.path.exists(path)
        assert os.stat(path).st_mode & 0o777 == 0o600
        ping = await d.services.ipc_client.request({"cmd": "ping"}, timeout=5.0)
        assert ping["pong"] is True
    finally:
        resp = await shutdown_served(d, task)
    assert resp["shutting_down"] is True
    assert not os.path.exists(path), "shutdown left a stale socket behind"
    assert d.device.disconnects >= 1


async def test_serve_restores_a_saved_mode(sock):
    """A daemon restart brings back the mode (and args) that were running."""
    storage = FakeStorage(state={"mode": "pattern", "args": {"name": "fade-blue", "speed": 12}})
    d = make_daemon(sock, storage=storage)
    task, _ = await serve_in_background(d)
    try:
        status = await d.services.ipc_client.request({"cmd": "status"}, timeout=5.0)
        assert status["mode"] == "pattern"
        assert status["desc"] == "pattern:fade-blue@12"
    finally:
        await shutdown_served(d, task)


async def test_serve_leaves_a_saved_off_state_off(sock):
    """'off' must stay off across a restart so the radio stays idle."""
    d = make_daemon(sock, storage=FakeStorage(state={"mode": "off", "args": {}}))
    task, _ = await serve_in_background(d)
    try:
        status = await d.services.ipc_client.request({"cmd": "status"}, timeout=5.0)
        assert status["mode"] == "off"
        assert d.mode_task is None
    finally:
        await shutdown_served(d, task)


async def test_second_daemon_refuses_to_steal_a_live_socket(sock):
    """Two daemons must never both own the socket; the newcomer bows out."""
    first = make_daemon(sock)
    task, path = await serve_in_background(first)
    try:
        second = make_daemon(sock)
        await asyncio.wait_for(second.serve(), timeout=5.0)
        assert second.mode_task is None
        # the original is still the one answering
        assert os.path.exists(path)
        ping = await first.services.ipc_client.request({"cmd": "ping"}, timeout=5.0)
        assert ping["pong"] is True
        assert not task.done()
    finally:
        await shutdown_served(first, task)


async def test_stale_socket_file_is_replaced(sock):
    """A socket left behind by a killed daemon is cleaned up, not fatal."""
    sock.write_text("")             # a leftover file with nobody listening
    d = make_daemon(sock)
    task, _ = await serve_in_background(d)
    try:
        ping = await d.services.ipc_client.request({"cmd": "ping"}, timeout=5.0)
        assert ping["pong"] is True
    finally:
        await shutdown_served(d, task)


async def _served_by(d, sock):
    server, _client = ipc_drivers(sock)
    await server.start(d)
    return server


async def test_malformed_json_gets_an_error_reply_not_a_dropped_connection(sock):
    """A client sending garbage must get a clean error, not silence."""
    d = make_daemon()
    server = await _served_by(d, sock)
    try:
        reader, writer = await open_raw(server)
        writer.write(b"this is not json\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        assert line, "daemon closed the connection instead of answering"
        resp = json.loads(line.decode())
        assert resp["ok"] is False
        assert "bad request" in resp["error"]
        writer.close()
    finally:
        await server.close()


async def test_daemon_survives_a_malformed_request_and_still_serves(sock):
    """One bad client must not affect the next good one."""
    d = make_daemon(sock)
    server = await _served_by(d, sock)
    try:
        reader, writer = await open_raw(server)
        writer.write(b"{not json\n")
        await writer.drain()
        await asyncio.wait_for(reader.readline(), timeout=2.0)
        writer.close()
        resp = await d.services.ipc_client.request({"cmd": "ping"}, timeout=2.0)
        assert resp["pong"] is True
    finally:
        await server.close()


@pytest.mark.parametrize("req", [[1, 2], "ping", 42])
async def test_a_non_object_request_is_refused_politely(req):
    """Valid JSON that is not an object gets an error reply, not an exception."""
    d = make_daemon()
    assert await d.handle_request(req) == {"ok": False,
                                           "error": "request must be a JSON object"}


async def test_a_handler_exception_becomes_an_error_reply(monkeypatch):
    """Anything a command raises is reported to the client, not propagated."""
    d = make_daemon()

    async def boom(req):
        raise KeyError("wat")

    monkeypatch.setattr(d, "handle", boom)
    resp = await d.handle_request({"cmd": "ping"})
    assert resp == {"ok": False, "error": "KeyError: 'wat'"}
