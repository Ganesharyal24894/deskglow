"""Fakes for the desktop-app tests: a scripted daemon client, a synchronous
bridge, and fake services. No daemon, no Bluetooth, no real tray."""
import asyncio
import copy

from fakes import FakeAutostart, FakeStorage

from deskglow.model.presets import get_preset
from deskglow.model.settings import DEFAULTS

MONITORS = {"DP-1": {"left": 0, "top": 0, "width": 2560, "height": 1440},
            "HDMI-1": {"left": 2560, "top": 0, "width": 1920, "height": 1080}}


def status(**over):
    """A realistic status reply (design sample values), with overrides."""
    base = dict(copy.deepcopy(DEFAULTS), ok=True, connected=True, configured=True,
                address="A4:C1:38:5E:22:9B", device_name="MELK-OA10", name="Desk strip",
                rssi=-58, sunset_available=True, last_solid="#FFB46E", brightness=80,
                mode="solid", args={"rgb": [255, 180, 110]}, color="#FFB46E",
                screen=None, audio_level=None, focus=None, desc="solid")
    base.update(over)
    return base


class FakeClient:
    """DaemonClient-shaped: records requests; `status` is what `status` returns;
    `replies[cmd]` scripts any other command (a dict, or callable(req))."""

    def __init__(self, **status_over):
        self.status = status(**status_over)
        self.requests = []
        self.replies = {"monitors": {"ok": True, "monitors": MONITORS}}
        self.daemon_up = True
        self.ensures = 0

    def sent(self, cmd=None):
        """Requests other than status polls (optionally only `cmd`)."""
        return [r for r in self.requests if r.get("cmd") != "status"
                and (cmd is None or r.get("cmd") == cmd)]

    async def ensure_daemon(self):
        self.ensures += 1
        return self.daemon_up

    async def request(self, req, timeout=25.0):
        self.requests.append(req)
        if req.get("cmd") == "status":
            return dict(self.status)
        if req.get("cmd") == "config" and "config" not in self.replies:
            self.status[req["key"]] = req["value"]      # like the daemon: it sticks
        if req.get("cmd") == "set_mode" and "set_mode" not in self.replies:
            self.status.update(mode=req["mode"], args=req.get("args") or {})
        reply = self.replies.get(req.get("cmd"), {"ok": True})
        if isinstance(reply, BaseException):
            raise reply
        return reply(req) if callable(reply) else reply


class SyncBridge:
    """The ThreadBridge API, run synchronously on the calling (Qt) thread."""

    def __init__(self, client):
        self.client = client

    def request(self, req, callback=None, timeout=25.0):
        reply = asyncio.run(self.client.request(req, timeout))
        if callback is not None:
            callback(reply if isinstance(reply, dict) else {"ok": False, "error": "none"})

    def call(self, fn, callback=None):
        try:
            result = fn()
        except Exception as e:
            result = e
        if callback is not None:
            callback(result)

    def stop(self):
        pass


class HeldBridge(SyncBridge):
    """Holds replies until release() — for in-flight/overlap tests."""

    def __init__(self, client):
        super().__init__(client)
        self.held = []

    def request(self, req, callback=None, timeout=25.0):
        self.held.append((req, callback))

    def release(self):
        req, callback = self.held.pop(0)
        super().request(req, callback)


class FakeHotkey:
    def __init__(self, ok=True):
        self.ok, self.registered, self.unregistered = ok, [], 0

    def register(self, sequence, callback):
        self.registered.append((sequence, callback))
        return self.ok

    def unregister(self):
        self.unregistered += 1


class FakeGuiServices:
    """The parts of Services the GUI process touches."""

    def __init__(self, hotkey=None, autostart=None):
        self.preset = get_preset()
        self.storage = FakeStorage({"address": "A4:C1:38:5E:22:9B"})
        self.autostart = autostart or FakeAutostart(enabled=True)
        self._hotkey = hotkey

    def hotkey(self):
        if self._hotkey is None:
            raise RuntimeError("global shortcuts is not available on this platform")
        return self._hotkey


def push(ctx, client, **status_over):
    """Make the fake daemon report `status_over` and deliver one status poll."""
    client.status.update(status_over)
    ctx.poller.poll()
    return ctx.status
