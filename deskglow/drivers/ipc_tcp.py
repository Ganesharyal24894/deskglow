"""IpcServer / IpcClient over TCP loopback, for Windows (no AF_UNIX asyncio).

The daemon listens on 127.0.0.1 with an OS-assigned port and writes
{"port": ..., "token": ...} to an endpoint file in the per-user local app data
dir. Any local user could reach a loopback port, so every connection must first
send that 64-hex-digit token as one JSON line; a wrong token is hung up on
before the request is read. Framing and limits are the unix driver's.
"""
import asyncio
import contextlib
import hmac
import json
import os
import secrets

from .ipc_framing import read_message, write_message
from .ipc_unix import serve_connection

ENDPOINT_NAME = "deskglowd.json"
HOST = "127.0.0.1"
AUTH_TIMEOUT = 5.0


def default_endpoint_path(dirs):
    return os.path.join(dirs.user_data_dir, ENDPOINT_NAME)


def read_endpoint(path):
    """(port, token) from the endpoint file. FileNotFoundError if missing;
    ConnectionRefusedError if unreadable (a half-written or foreign file)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        data = json.loads(text)
        return int(data["port"]), str(data["token"])
    except (ValueError, KeyError, TypeError):
        raise ConnectionRefusedError(f"unusable IPC endpoint file {path}") from None


class TcpIpcServer:
    def __init__(self, endpoint_file, host=HOST, token_factory=None):
        self.endpoint_file = endpoint_file
        self.host = host
        self.address = endpoint_file
        self._token_factory = token_factory or (lambda: secrets.token_hex(32))
        self._server = None
        self.token = None
        self.port = None

    def exists(self):
        return os.path.exists(self.endpoint_file)

    def remove_stale(self):
        os.unlink(self.endpoint_file)

    async def _on_connect(self, handler, reader, writer):
        try:
            sent = await asyncio.wait_for(read_message(reader), AUTH_TIMEOUT)
        except Exception:
            sent = None
        if not isinstance(sent, str) or not hmac.compare_digest(
                sent.encode(), self.token.encode()):
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return
        await serve_connection(handler, reader, writer)

    async def start(self, handler):
        self.token = self._token_factory()

        async def on_connect(reader, writer):
            await self._on_connect(handler, reader, writer)

        self._server = await asyncio.start_server(on_connect, host=self.host, port=0)
        self.port = self._server.sockets[0].getsockname()[1]
        self.address = f"{self.host}:{self.port} ({self.endpoint_file})"
        self._write_endpoint()

    def _write_endpoint(self):
        directory = os.path.dirname(self.endpoint_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.endpoint_file + ".tmp"
        # O_EXCL-free but 0600 where the OS honours modes; on Windows the
        # per-user %LOCALAPPDATA% ACL is what keeps other users out.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"port": self.port, "token": self.token, "pid": os.getpid()}, f)
        os.replace(tmp, self.endpoint_file)

    async def close(self):
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()

    def remove(self):
        with contextlib.suppress(Exception):
            os.unlink(self.endpoint_file)


class TcpIpcClient:
    def __init__(self, endpoint_file):
        self.endpoint_file = endpoint_file

    async def request(self, message, timeout=25.0):
        """Authenticate, send one request, return the one-line JSON reply."""
        port, token = read_endpoint(self.endpoint_file)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(HOST, port), timeout=5.0)
        try:
            await write_message(writer, token)
            await write_message(writer, message)
            return await asyncio.wait_for(read_message(reader), timeout=timeout)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
