"""Daemon commands that manage which strip is used, plus favourites and the
monitor list. Scanning happens here, in the daemon, so the desktop app never
touches the radio itself (on Windows it must stay in one process)."""
import contextlib

from ..model import settings_rules
from .discovery import scan_candidates

SCAN_DEFAULT = 8.0
SCAN_MAX = 30.0


def _error(e):
    return {"ok": False, "error": str(e)}


class StripCommands:
    """Mixed into Daemon. Expects device, settings, state, services, _mode_lock."""

    rssi = None   # last signal strength seen for the configured strip, dBm

    async def _cmd_scan(self, req):
        timeout = req.get("timeout", SCAN_DEFAULT)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            return {"ok": False, "error": "timeout must be a number of seconds"}
        timeout = max(1.0, min(SCAN_MAX, float(timeout)))
        try:
            found = await scan_candidates(self.services.scanner, timeout, self.services.preset)
        except Exception as e:
            return {"ok": False, "error": f"scan failed: {e}"}
        mine = (self.device.address or "").upper()
        for c in found:
            if mine and c["address"].upper() == mine and c["rssi"] is not None:
                self.rssi = c["rssi"]
        return {"ok": True, "candidates": found}

    async def _cmd_set_address(self, req):
        try:
            addr = settings_rules.address(req.get("address"))
        except ValueError as e:
            return _error(e)
        name = req.get("name")
        name = name.strip()[:settings_rules.MAX_NAME] if isinstance(name, str) else None
        async with self._mode_lock:
            self.settings.set_address(addr, name or None)
            self.rssi = req.get("rssi") if isinstance(req.get("rssi"), int) else None
            await self.device.disconnect()        # let go of the previous strip
            self.device.reset_backoff()
            await self._set_mode(self.mode_name, self.mode_args)
        return {"ok": True, "address": addr, "configured": bool(self.device.address)}

    async def _cmd_forget(self, req):
        async with self._mode_lock:
            await self._set_mode("off", {})
            self._cancel_idle()
            await self.device.disconnect()
            self.settings.forget()
            self.rssi = None
        return {"ok": True, "configured": bool(self.device.address)}

    async def _cmd_monitors(self, req):
        try:
            source = self.services.screen()
        except Exception as e:
            return _error(e)
        try:
            monitors = await source.monitors()
        except Exception as e:
            return _error(e)
        finally:
            with contextlib.suppress(Exception):
                source.close()
        return {"ok": True, "monitors": dict(monitors or {})}

    async def _cmd_favourite_add(self, req):
        return self._update_favourites(settings_rules.add_favourite, req)

    async def _cmd_favourite_remove(self, req):
        return self._update_favourites(settings_rules.remove_favourite, req)

    def _update_favourites(self, fn, req):
        try:
            favs = fn(list(self.state.get("favourites") or []), req.get("color"))
        except ValueError as e:
            return _error(e)
        self.state["favourites"] = favs
        self.settings.save_state(self.state)
        return {"ok": True, "favourites": favs}
