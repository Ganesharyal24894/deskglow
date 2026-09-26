"""The daemon's command surface: one JSON request in, one JSON reply out."""
from ..model.settings import CONFIG_KEYS, validate_setting
from .status import build_status

# Settings whose new value a running mode only reads when it starts: changing
# one restarts these modes so the change shows at once.
RESTART_ON_CHANGE = {
    "brightness": ("solid", "circadian", "pattern"),
    "max_brightness": ("solid", "circadian", "pattern"),
    "screen_monitor": ("screen",),
    "screen_style": ("screen",),
}


class CommandHandler:
    """Mixed into Daemon; implements the IpcHandler service interface."""

    # ---- IpcHandler -------------------------------------------------------

    def malformed(self, error):
        # malformed JSON / oversized line: answer, don't just hang up
        return {"ok": False, "error": f"bad request: {type(error).__name__}: {error}"}

    async def handle_request(self, req):
        if not isinstance(req, dict):
            return {"ok": False, "error": "request must be a JSON object"}
        try:
            return await self.handle(req)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ---- commands ---------------------------------------------------------

    async def handle(self, req):
        cmd = req.get("cmd")
        if cmd == "ping":
            return {"ok": True, "pong": True}
        if cmd == "status":
            return build_status(self)
        handler = self._commands().get(cmd)
        if handler is None:
            return {"ok": False, "error": f"unknown cmd {cmd!r}"}
        return await handler(req)

    def _commands(self):
        return {
            "reload": self._cmd_reload, "set_mode": self._cmd_set_mode,
            "off": self._cmd_off, "on": self._cmd_on, "toggle": self._cmd_toggle,
            "reset": self._cmd_reset, "config": self._cmd_config,
            "shutdown": self._cmd_shutdown, "focus_pause": self._cmd_focus_pause,
            # strip management (controller/strip_commands.py)
            "scan": self._cmd_scan, "set_address": self._cmd_set_address,
            "forget": self._cmd_forget, "monitors": self._cmd_monitors,
            "favourite_add": self._cmd_favourite_add,
            "favourite_remove": self._cmd_favourite_remove,
        }

    async def _cmd_reload(self, req):
        # picked up a newly-configured address: clear backoff and reconnect
        async with self._mode_lock:
            self.device.reset_backoff()
            await self._set_mode(self.mode_name, self.mode_args)
        return {"ok": True, "configured": bool(self.device.address)}

    async def _cmd_set_mode(self, req):
        await self.set_mode(req.get("mode"), req.get("args") or {})
        return {"ok": True, "mode": self.mode_name, "desc": self.mode_desc}

    async def _cmd_off(self, req):
        await self.set_mode("off", {})
        return {"ok": True}

    async def _cmd_on(self, req):
        await self.turn_on()
        return {"ok": True, "mode": self.mode_name, "desc": self.mode_desc}

    async def _cmd_toggle(self, req):
        if self.mode_name == "off":
            await self.turn_on()
        else:
            await self.set_mode("off", {})
        return {"ok": True, "mode": self.mode_name, "on": self.mode_name != "off"}

    async def _cmd_shutdown(self, req):
        self._stop.set()
        return {"ok": True, "shutting_down": True}

    async def _cmd_focus_pause(self, req):
        ctx = getattr(self, "mode_ctx", None)
        if self.mode_name != "pomodoro" or ctx is None:
            return {"ok": False, "error": "no focus timer is running"}
        paused = req.get("paused", True)
        if not isinstance(paused, bool):
            return {"ok": False, "error": "paused must be true or false"}
        ctx.controls["paused"] = paused
        return {"ok": True, "paused": paused}

    async def _cmd_reset(self, req):
        # stop any mode, force a known-good static state, reset the ceiling
        async with self._mode_lock:
            self._gen += 1
            self._cancel_idle()
            await self._stop_mode()
            self.state["max_brightness"] = 100
            self.settings.save_state(self.state)
            try:
                await self.device.reset_known_good()
            except Exception as e:
                return {"ok": False, "error": f"strip unreachable: {e}"}
            # hold that state as a solid-white mode
            await self._set_mode("solid", {"rgb": [255, 255, 255]})
        return {"ok": True, "reset": True}

    async def _cmd_config(self, req):
        key, val = req.get("key"), req.get("value")
        if key not in CONFIG_KEYS:
            return {"ok": False, "error": f"unknown config key {key!r}"}
        try:
            val = validate_setting(key, val)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        changed = self.state.get(key) != val
        self.state[key] = val
        self.settings.save_state(self.state)
        if changed and self.mode_name in RESTART_ON_CHANGE.get(key, ()):
            await self.set_mode(self.mode_name, self.mode_args)
        return {"ok": True, key: val}
