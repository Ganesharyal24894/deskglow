"""IpcServer / IpcClient over a unix domain socket private to the user."""
import asyncio
import contextlib
import os

from .ipc_framing import read_message, write_message

SOCKET_NAME = "deskglowd.sock"


def default_socket_path(env=None):
    """$XDG_RUNTIME_DIR/deskglowd.sock, else a uid-scoped path in /tmp."""
    env = os.environ if env is None else env
    runtime = env.get("XDG_RUNTIME_DIR")
    if runtime and os.path.isdir(runtime):
        return os.path.join(runtime, SOCKET_NAME)
    return f"/tmp/deskglowd-{os.getuid()}.sock"


def macos_socket_path(dirs, private_dir=None):
    """<platformdirs runtime dir, created 0700>/deskglowd.sock on macOS.

    Kept short: macOS caps AF_UNIX paths at 104 bytes."""
    from .paths import private_dir as make_private
    return os.path.join((private_dir or make_private)(dirs.user_runtime_dir), SOCKET_NAME)


async def serve_connection(handler, reader, writer):
    """One request, one reply, then hang up. Malformed input gets an error
    reply instead of a dropped connection."""
    try:
        try:
            req = await read_message(reader)
        except Exception as e:
            await write_message(writer, handler.malformed(e))
            return
        if req is None:
            return
        await write_message(writer, await handler.handle_request(req))
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


class UnixIpcServer:
    def __init__(self, path):
        self.path = path
        self.address = path
        self._server = None

    def exists(self):
        return os.path.exists(self.path)

    def remove_stale(self):
        os.unlink(self.path)

    async def start(self, handler):
        async def on_connect(reader, writer):
            await serve_connection(handler, reader, writer)

        # Bind under a restrictive umask so the socket is never briefly
        # accessible to other local users between creation and chmod.
        old_umask = os.umask(0o177)
        try:
            self._server = await asyncio.start_unix_server(on_connect, path=self.path)
        finally:
            os.umask(old_umask)
        os.chmod(self.path, 0o600)

    async def close(self):
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()

    def remove(self):
        with contextlib.suppress(Exception):
            os.unlink(self.path)


class UnixIpcClient:
    def __init__(self, path):
        self.path = path

    async def request(self, message, timeout=25.0):
        """Connect, send one request, return the one-line JSON reply."""
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(self.path), timeout=5.0)
        try:
            await write_message(writer, message)
            return await asyncio.wait_for(read_message(reader), timeout=timeout)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
