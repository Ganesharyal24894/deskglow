"""Client side of the daemon protocol: make sure a daemon runs, then ask it.

Prefers the installed login service so the installed code runs (and no rogue
client-spawned daemon holds the endpoint); falls back to spawning one, but only
one caller per process may do that at a time.
"""
import asyncio
import time

# How long to wait for a daemon we just asked to start, and how often to poll.
# Module level so tests can shorten them.
START_WAIT = 10.0
POLL_INTERVAL = 0.25


class DaemonClient:
    def __init__(self, ipc_client, autostart, process):
        self.ipc = ipc_client
        self.autostart = autostart
        self.process = process

    async def ping(self):
        try:
            r = await self.ipc.request({"cmd": "ping"}, timeout=2.0)
            return bool(r and r.get("pong"))
        except Exception:
            return False

    async def wait_for_daemon(self, timeout=None):
        """Poll until the daemon answers, or the timeout expires."""
        timeout = START_WAIT if timeout is None else timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(POLL_INTERVAL)
            if await self.ping():
                return True
        return False

    def _start_service(self):
        try:
            return bool(self.autostart.start())
        except Exception:
            return False

    async def ensure_daemon(self):
        if await self.ping():
            return True
        if self._start_service() and await self.wait_for_daemon():
            return True
        # Fall back to spawning one ourselves (the service isn't installed), but
        # only one caller may do that — polling clients would otherwise each
        # fork their own daemon while the first was still starting up.
        if not self.process.try_begin_spawn():
            return await self.wait_for_daemon()   # someone else is already starting it
        try:
            if await self.ping():                 # it came up while we waited
                return True
            self.process.spawn_daemon()
            return await self.wait_for_daemon()
        finally:
            self.process.end_spawn()

    async def request(self, req, timeout=25.0):
        """One request to the (running) daemon; the raw reply or None."""
        return await self.ipc.request(req, timeout=timeout)
