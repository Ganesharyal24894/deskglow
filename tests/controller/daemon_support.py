"""Helpers shared by the daemon tests (tests/controller/test_daemon_*.py)."""
import asyncio
import sys

from fakes import FakeDevice, FakeStorage, make_services

from deskglow.controller.daemon import Daemon
from deskglow.drivers.ipc_framing import write_message
from deskglow.drivers.ipc_tcp import TcpIpcClient, TcpIpcServer
from deskglow.drivers.ipc_unix import UnixIpcClient, UnixIpcServer

# The IPC this OS really uses: AF_UNIX, or loopback TCP + an endpoint file on Windows.
ENDPOINT_NAME = "d.json" if sys.platform == "win32" else "d.sock"


def ipc_drivers(endpoint):
    """(server, client) at `endpoint` (a socket path, or the TCP endpoint file)."""
    if sys.platform == "win32":
        return TcpIpcServer(str(endpoint)), TcpIpcClient(str(endpoint))
    return UnixIpcServer(str(endpoint)), UnixIpcClient(str(endpoint))


def endpoint_of(server):
    return getattr(server, "path", None) or server.endpoint_file


async def open_raw(server):
    """A raw (reader, writer) to a started server, past any auth handshake."""
    if isinstance(server, TcpIpcServer):
        reader, writer = await asyncio.open_connection(server.host, server.port)
        await write_message(writer, server.token)
        return reader, writer
    return await asyncio.open_unix_connection(server.path)


def make_daemon(sock=None, storage=None, **device_kw):
    """A Daemon on fake services whose strip is a FakeDevice and whose watchdog
    never sleeps. With `sock`, IPC uses this OS's real driver at that endpoint."""
    kw = {"storage": storage or FakeStorage()}
    if sock is not None:
        server, client = ipc_drivers(sock)
        kw.update(ipc_server=server, ipc_client=client)
    d = Daemon(make_services(**kw), log=lambda _m: None)
    d.device = FakeDevice(**device_kw)

    async def _no_watchdog():
        await asyncio.sleep(0)

    d._watchdog = _no_watchdog
    return d


async def quiesce(d):
    """Stop anything the daemon left running so the loop closes cleanly."""
    d._cancel_idle()
    await d._stop_mode()


async def serve_in_background(d, timeout=5.0):
    """Start d.serve() and wait until it really answers on its socket."""
    task = asyncio.ensure_future(d.serve())
    client = d.services.ipc_client
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        if task.done():
            await task
            break
        try:
            reply = await client.request({"cmd": "ping"}, timeout=1.0)
            if reply and reply.get("pong"):
                break
        except Exception:
            pass
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("serve() never started answering")
        await asyncio.sleep(0.005)
    return task, endpoint_of(d.services.ipc_server)


async def shutdown_served(d, task):
    resp = await d.services.ipc_client.request({"cmd": "shutdown"}, timeout=5.0)
    await asyncio.wait_for(task, timeout=5.0)
    return resp


class BoomMode:
    """A mode that dies the instant it is started."""
    name = "boom"

    def describe(self):
        return "boom"

    async def run(self, ctx):
        raise RuntimeError("kaput")
