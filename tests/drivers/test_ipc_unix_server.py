"""UnixIpcServer, serve_connection and default_socket_path (new driver tests)."""
import asyncio
import os
import stat

import sys

import pytest
from ipc_support import FakeWriter, stream_of

from deskglow.drivers.ipc_unix import (UnixIpcClient, UnixIpcServer, default_socket_path,
                                       serve_connection)


posix_only = pytest.mark.skipif(sys.platform == "win32",
                                reason="AF_UNIX asyncio servers / uids are POSIX-only; "
                                       "Windows uses ipc_tcp")


class Handler:
    """A recording IpcHandler."""

    def __init__(self):
        self.requests = []
        self.errors = []

    async def handle_request(self, request):
        self.requests.append(request)
        return {"ok": True, "got": request}

    def malformed(self, error):
        self.errors.append(error)
        return {"ok": False, "error": "malformed"}


# ------------------------------------------------------- default_socket_path --

def test_socket_path_uses_xdg_runtime_dir(tmp_path):
    run = tmp_path / "run-1000"
    run.mkdir()
    assert default_socket_path({"XDG_RUNTIME_DIR": str(run)}) == str(run / "deskglowd.sock")


@posix_only
@pytest.mark.parametrize("env", [{}, {"XDG_RUNTIME_DIR": ""}, {"XDG_RUNTIME_DIR": "/nonexistent/gone"}],
                         ids=["unset", "empty", "missing-dir"])
def test_socket_path_falls_back_to_a_uid_scoped_tmp_path(env):
    """No usable runtime dir -> a per-user socket in /tmp, never a dead path."""
    assert default_socket_path(env) == f"/tmp/deskglowd-{os.getuid()}.sock"


def test_socket_path_works_without_os_getuid(monkeypatch):
    """Regression (Windows CI): os.getuid does not exist on Windows, and the
    Linux wiring is built there in tests -> the fallback must not crash."""
    monkeypatch.delattr(os, "getuid", raising=False)
    monkeypatch.setenv("USERNAME", "ada")
    assert default_socket_path({}) == "/tmp/deskglowd-ada.sock"


def test_socket_path_reads_the_process_environment_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert default_socket_path() == str(tmp_path / "deskglowd.sock")
    assert default_socket_path() == default_socket_path(), "CLI and daemon must meet"


# ------------------------------------------------------------ serve_connection --

async def test_serve_connection_passes_any_decoded_request_to_the_handler():
    """Validation (dict or not) is the controller's job, not the transport's."""
    h, w = Handler(), FakeWriter()
    await serve_connection(h, stream_of(b"[1, 2]\n"), w)
    assert h.requests == [[1, 2]]
    assert bytes(w.buf) == b'{"ok": true, "got": [1, 2]}\n'
    assert w.closed


async def test_serve_connection_answers_garbage_with_the_malformed_reply():
    h, w = Handler(), FakeWriter()
    await serve_connection(h, stream_of(b"not json\n"), w)
    assert h.requests == [] and len(h.errors) == 1
    assert isinstance(h.errors[0], ValueError)
    assert bytes(w.buf) == b'{"ok": false, "error": "malformed"}\n'
    assert w.closed


async def test_serve_connection_ignores_a_peer_that_hung_up_before_the_reply():
    """Regression: a client that disconnects early (e.g. a killed GUI) made
    the daemon log an unhandled ConnectionResetError traceback."""
    class GoneWriter(FakeWriter):
        async def drain(self):
            raise ConnectionResetError("Connection lost")

    h, w = Handler(), GoneWriter()
    await serve_connection(h, stream_of(b'{"cmd": "ping"}\n'), w)
    assert h.requests == [{"cmd": "ping"}] and w.closed


async def test_serve_connection_writes_nothing_when_the_peer_sends_nothing():
    h, w = Handler(), FakeWriter()
    await serve_connection(h, stream_of(b""), w)
    assert h.requests == [] and h.errors == []
    assert bytes(w.buf) == b""
    assert w.closed, "the connection must still be closed"


# --------------------------------------------------------------- UnixIpcServer --

@posix_only
async def test_server_socket_is_private_and_the_umask_is_restored(tmp_path):
    path = tmp_path / "d.sock"
    server = UnixIpcServer(str(path))
    before = os.umask(0o022)
    os.umask(before)
    await server.start(Handler())
    try:
        assert stat.S_ISSOCK(os.stat(path).st_mode)
        assert os.stat(path).st_mode & 0o777 == 0o600
        after = os.umask(before)
        assert after == before, "start() leaked its restrictive umask"
    finally:
        await server.close()
        server.remove()


@posix_only
async def test_server_binds_under_a_restrictive_umask(tmp_path, monkeypatch):
    """The socket must never exist world-accessible, even before the chmod."""
    seen = []
    real_start = asyncio.start_unix_server

    async def spy(*a, **kw):
        current = os.umask(0)
        os.umask(current)
        seen.append(current)
        return await real_start(*a, **kw)

    monkeypatch.setattr(asyncio, "start_unix_server", spy)
    server = UnixIpcServer(str(tmp_path / "d.sock"))
    await server.start(Handler())
    await server.close()
    assert seen == [0o177]


@posix_only
async def test_server_round_trips_through_the_client(tmp_path):
    path = str(tmp_path / "d.sock")
    server, h = UnixIpcServer(path), Handler()
    await server.start(h)
    try:
        assert server.address == path
        assert await UnixIpcClient(path).request({"cmd": "ping"}, timeout=5.0) == {
            "ok": True, "got": {"cmd": "ping"}}
    finally:
        await server.close()


@posix_only
async def test_close_stops_accepting_connections(tmp_path):
    path = str(tmp_path / "d.sock")
    server = UnixIpcServer(path)
    await server.start(Handler())
    await server.close()
    await server.close()                  # idempotent
    with pytest.raises(OSError):
        await UnixIpcClient(path).request({"cmd": "ping"}, timeout=1.0)


def test_exists_remove_stale_and_remove(tmp_path):
    path = tmp_path / "d.sock"
    server = UnixIpcServer(str(path))
    assert not server.exists()
    path.write_text("")                   # a leftover from a killed daemon
    assert server.exists()
    server.remove_stale()
    assert not server.exists()
    path.write_text("")
    server.remove()
    assert not path.exists()
    server.remove()                       # already gone: must not raise


def test_macos_socket_lives_in_a_private_runtime_dir(tmp_path):
    from types import SimpleNamespace

    from deskglow.drivers.ipc_unix import macos_socket_path
    made = []
    dirs = SimpleNamespace(user_runtime_dir=str(tmp_path / "rt"))
    path = macos_socket_path(dirs, private_dir=lambda p: made.append(p) or p)
    assert made == [str(tmp_path / "rt")]
    assert path == str(tmp_path / "rt" / "deskglowd.sock")
