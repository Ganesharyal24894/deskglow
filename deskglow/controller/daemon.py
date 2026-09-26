"""The background daemon: owns the strip link, runs one mode at a time, and
serves commands from clients over the IpcServer service."""
import contextlib
import logging

from .commands import CommandHandler
from .device import Device
from .lifecycle import ModeLifecycle
from .power import PowerMixin
from .settings import SettingsStore
from .strip_commands import StripCommands
from .sunset import SunsetWatcher

_default_log = logging.getLogger("deskglow.daemon").info


class Daemon(CommandHandler, StripCommands, PowerMixin, ModeLifecycle):
    def __init__(self, services, log=None, clock=None):
        self.services = services
        self.log = log or _default_log
        self.settings = SettingsStore(services.storage)
        self.state = self.settings.load_state()
        self.device = Device(services.link, services.encoder,
                             address_source=self.settings.get_address, logger=self.log)
        self._init_lifecycle()
        kw = {"clock": clock} if clock is not None else {}
        self.sunset = SunsetWatcher(
            services.location, is_enabled=lambda: bool(self.state.get("sunset_on")),
            is_off=lambda: self.mode_name == "off", turn_on=self.turn_on_solid,
            log=self.log, **kw)

    def request_stop(self):
        """Ask serve() to shut down (e.g. from a signal handler)."""
        self._stop.set()

    async def serve(self):
        server = self.services.ipc_server
        # clear a stale endpoint (only if no live daemon answers there)
        if server.exists():
            if await self._is_alive():
                self.log(f"another daemon already listening at {server.address}; exiting")
                return
            server.remove_stale()
        await server.start(self)
        self.log(f"listening on {server.address}")
        self.start_background_tasks()

        # restore last mode (off stays off => radio idle)
        restore = self.state.get("mode", "off")
        if restore and restore != "off":
            self.log(f"restoring mode: {restore}")
            with contextlib.suppress(Exception):
                await self.set_mode(restore, self.state.get("args", {}))

        try:
            await self._stop.wait()
        finally:
            await server.close()
        self.log("shutting down")
        await self._stop_mode()
        await self.shutdown_background_tasks()
        await self.device.disconnect()
        server.remove()

    async def _is_alive(self):
        try:
            resp = await self.services.ipc_client.request({"cmd": "ping"}, timeout=2.0)
            return bool(resp and resp.get("pong"))
        except Exception:
            return False
