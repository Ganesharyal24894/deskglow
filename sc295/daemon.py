"""The background daemon: owns the BLE link, runs one mode at a time, and serves
commands from the CLI over a unix socket.

Speaker-friendly: while the mode is 'off' the daemon releases the BLE link after
a short idle timeout, so the radio behaves as if the strip weren't connected.
"""
import asyncio
import contextlib
import os
import signal
import sys
import time

from . import ipc, modes
from .config import (IDLE_DISCONNECT, load_state, save_state, socket_path)
from .device import Device


def _log(msg):
    print(f"[sc295d] {msg}", file=sys.stderr, flush=True)


class Daemon:
    def __init__(self):
        self.state = load_state()
        self.device = Device(logger=_log)
        self.mode_task = None
        self.mode_name = "off"
        self.mode_desc = "off"
        self.mode_args = {}
        self._idle_task = None
        self._stop = asyncio.Event()

    # ---- mode lifecycle ---------------------------------------------------

    async def _run_mode(self, mode):
        ctx = modes.ModeContext(self.device, self.state, _log)
        try:
            await mode.run(ctx)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a mode crashing must not kill the daemon
            _log(f"mode {mode.name} error: {type(e).__name__}: {e}")
            self.mode_name = "off"
            self.mode_desc = f"off (after {mode.name} error)"

    async def _stop_mode(self):
        if self.mode_task and not self.mode_task.done():
            self.mode_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.mode_task
        self.mode_task = None

    def _cancel_idle(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def _watchdog(self):
        """Safety net: if the strip is unreachable for a very long stretch, exit
        so systemd restarts us fresh — this frees any leaked D-Bus/socket FDs
        before they could approach the per-user bus limit."""
        while not self._stop.is_set():
            await asyncio.sleep(60)
            # only recycle for a *real* connectivity problem, not because the
            # strip simply isn't configured yet
            if self.device.address and self.device.consecutive_failures >= 40:
                _log(f"persistent connect failures "
                     f"(x{self.device.consecutive_failures}); exiting for a clean "
                     f"restart to release resources")
                os._exit(1)  # Restart=on-failure brings us back clean

    async def _idle_then_disconnect(self):
        try:
            await asyncio.sleep(IDLE_DISCONNECT)
            if self.mode_name == "off":
                await self.device.disconnect()
        except asyncio.CancelledError:
            pass

    async def set_mode(self, name, args):
        self._cancel_idle()
        await self._stop_mode()
        args = args or {}
        if name == "off":
            self.mode_name = "off"
            self.mode_desc = "off"
            self.mode_args = {}
            with contextlib.suppress(Exception):
                await self.device.power(False)
            self._idle_task = asyncio.create_task(self._idle_then_disconnect())
            self._persist()
            return
        if name == "screen":
            style = args.get("style")
            if style:
                self.state["screen_style"] = style
                save_state(self.state)
        try:
            mode = modes.build(name, args)
        except Exception as e:
            _log(f"cannot start mode {name!r} ({e}); staying off")
            self.mode_name = "off"
            self.mode_desc = f"off (bad {name})"
            self.mode_args = {}
            self._persist()
            return
        # A prior `off` powered the strip down; if the link is still open the
        # per-connect power-on won't fire, so explicitly power on before the mode
        # starts sending colors (otherwise color writes are ignored while off).
        with contextlib.suppress(Exception):
            await self.device.power(True)
        self.mode_name = name
        self.mode_desc = mode.describe()
        self.mode_args = args
        self.mode_task = asyncio.create_task(self._run_mode(mode))
        self._persist()

    def _persist(self):
        self.state["mode"] = self.mode_name
        self.state["args"] = self.mode_args   # so args-bearing modes restore too
        with contextlib.suppress(Exception):
            save_state(self.state)

    # ---- command handling -------------------------------------------------

    async def handle(self, req):
        cmd = req.get("cmd")
        if cmd == "ping":
            return {"ok": True, "pong": True}
        if cmd == "status":
            return {"ok": True, "mode": self.mode_name, "desc": self.mode_desc,
                    "connected": self.device.connected,
                    "configured": bool(self.device.address),
                    "address": self.device.address,
                    "screen_monitor": self.state.get("screen_monitor"),
                    "screen_style": self.state.get("screen_style"),
                    "max_brightness": self.state.get("max_brightness")}
        if cmd == "reload":
            # picked up a newly-configured address: clear backoff and reconnect
            self.device.reset_backoff()
            await self.set_mode(self.mode_name, self.mode_args)
            return {"ok": True, "configured": bool(self.device.address)}
        if cmd == "set_mode":
            await self.set_mode(req.get("mode"), req.get("args") or {})
            return {"ok": True, "mode": self.mode_name, "desc": self.mode_desc}
        if cmd == "off":
            await self.set_mode("off", {})
            return {"ok": True}
        if cmd == "reset":
            # stop any mode, force a known-good static state, reset the ceiling
            self._cancel_idle()
            await self._stop_mode()
            self.state["max_brightness"] = 100
            save_state(self.state)
            try:
                await self.device.reset_known_good()
            except Exception as e:
                return {"ok": False, "error": f"strip unreachable: {e}"}
            # hold that state as a solid-white mode
            await self.set_mode("solid", {"rgb": [255, 255, 255]})
            return {"ok": True, "reset": True}
        if cmd == "config":
            key, val = req.get("key"), req.get("value")
            if key not in ("screen_monitor", "screen_style", "max_brightness"):
                return {"ok": False, "error": f"unknown config key {key!r}"}
            self.state[key] = val
            save_state(self.state)
            return {"ok": True, key: val}
        if cmd == "shutdown":
            self._stop.set()
            return {"ok": True, "shutting_down": True}
        return {"ok": False, "error": f"unknown cmd {cmd!r}"}

    async def _client(self, reader, writer):
        try:
            req = await ipc.read_message(reader)
            if req is None:
                return
            try:
                resp = await self.handle(req)
            except Exception as e:
                resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            await ipc.write_message(writer, resp)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    # ---- server bootstrap -------------------------------------------------

    async def serve(self):
        path = socket_path()
        # clear a stale socket (only if no live daemon answers there)
        if os.path.exists(path):
            if await self._is_alive(path):
                _log(f"another daemon already listening at {path}; exiting")
                return
            os.unlink(path)
        server = await asyncio.start_unix_server(self._client, path=path)
        os.chmod(path, 0o600)
        _log(f"listening on {path}")

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._stop.set)

        asyncio.create_task(self._watchdog())

        # restore last mode (off stays off => radio idle)
        restore = self.state.get("mode", "off")
        if restore and restore != "off":
            _log(f"restoring mode: {restore}")
            with contextlib.suppress(Exception):
                await self.set_mode(restore, self.state.get("args", {}))

        async with server:
            await self._stop.wait()
        _log("shutting down")
        await self._stop_mode()
        await self.device.disconnect()
        with contextlib.suppress(Exception):
            os.unlink(path)

    @staticmethod
    async def _is_alive(path):
        try:
            resp = await ipc.request(path, {"cmd": "ping"}, timeout=2.0)
            return bool(resp and resp.get("pong"))
        except Exception:
            return False


def main():
    try:
        asyncio.run(Daemon().serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
