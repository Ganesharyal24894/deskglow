"""Fakes implementing the deskglow service interfaces, shared by every test.

Import with `from fakes import ...` (tests/ is on sys.path via conftest). Nothing
here touches a radio, a display, an audio device or the network.
"""
import asyncio
import threading

from deskglow.model.presets import get_preset
from deskglow.services.container import Services
from deskglow.services.scanner import Advert
from deskglow.view.strip import StripEncoder

ENCODER = StripEncoder(get_preset())


class FakeDevice:
    """Stand-in for controller.device.Device: records everything written."""

    def __init__(self, latency=0.0, address="AA:BB:CC:DD:EE:FF"):
        self.address = address
        self.encoder = ENCODER
        self.connected = True
        self.consecutive_failures = 0
        self.latency = latency
        self.colors = []          # [(r, g, b), ...]
        self.last_rgb = None      # mirrors Device.last_rgb
        self.frames = []          # raw protocol frames
        self.power_calls = []     # [True/False, ...]
        self.disconnects = 0
        self.backoff_resets = 0
        self.fail_with = None     # set to an Exception to make writes fail

    async def _tick(self):
        if self.latency:
            await asyncio.sleep(self.latency)
        if self.fail_with is not None:
            raise self.fail_with

    async def set_rgb(self, r, g, b, force=False):
        await self._tick()
        self.last_rgb = (int(r), int(g), int(b))
        self.colors.append(self.last_rgb)

    async def send_frame(self, frame, reliable=False):
        await self._tick()
        self.frames.append(bytes(frame))

    async def power(self, on, reliable=False):
        await self._tick()
        self.power_calls.append(bool(on))

    async def reset_known_good(self):
        await self._tick()
        self.frames.append(b"RESET")

    async def disconnect(self):
        self.disconnects += 1

    def reset_backoff(self):
        self.backoff_resets += 1


class FakeStorage:
    """In-memory Storage. `state` is None until something is saved."""

    def __init__(self, config=None, state=None, override=None):
        self.config, self.state, self.override = dict(config or {}), state, override
        self.config_saves = self.state_saves = 0

    def load_config(self):
        return dict(self.config)

    def save_config(self, cfg):
        self.config_saves += 1
        self.config = dict(cfg)

    def load_state(self):
        return None if self.state is None else dict(self.state)

    def save_state(self, state):
        self.state_saves += 1
        self.state = dict(state)

    def address_override(self):
        return self.override or None

    def config_dir(self):
        return "/fake/config/deskglow"

    def log_path(self):
        return "/fake/config/deskglow/daemon.log"


class FakeScanner:
    def __init__(self, adverts=(), error=None):
        self.adverts = [a if isinstance(a, Advert) else Advert(**a) for a in adverts]
        self.error = error
        self.timeouts = []

    async def scan(self, timeout):
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return list(self.adverts)


class FakeIpcClient:
    """Scripted IpcClient: `reply` is a value, an exception, or a callable(req)."""

    def __init__(self, reply=None):
        self.reply = reply
        self.requests = []

    async def request(self, message, timeout=25.0):
        self.requests.append(message)
        r = self.reply
        if isinstance(r, BaseException):
            raise r
        return r(message) if callable(r) else r


class FakeAutostart:
    def __init__(self, result=False, enabled=False, error=None):
        # `error` is raised by set_enabled (an OSError, say)
        self.result, self.enabled, self.error = result, enabled, error
        self.calls, self.set_calls = 0, []

    def start(self):
        self.calls += 1
        return self.result

    def is_enabled(self):
        return self.enabled

    def set_enabled(self, enabled):
        self.set_calls.append(bool(enabled))
        if self.error is not None:
            raise self.error
        self.enabled = bool(enabled)


class ExitCalled(Exception):
    """Raised by FakeProcessControl.exit_for_restart so the test process survives."""


class FakeProcessControl:
    def __init__(self):
        self.spawns = 0
        self.exits = []
        self._lock = threading.Lock()

    def spawn_daemon(self):
        self.spawns += 1

    def try_begin_spawn(self):
        return self._lock.acquire(blocking=False)

    def end_spawn(self):
        self._lock.release()

    def exit_for_restart(self, code=1):
        self.exits.append(code)
        raise ExitCalled(code)


class FakeLink:
    """Minimal LightLink; the device tests use a richer harness of their own."""

    def __init__(self):
        self.dropped = []
        self.resets = []
        self.reset_error = None

    def session(self, target, timeout):
        raise OSError("FakeLink has no radio")

    async def find(self, address, timeout):
        return None

    def drop_bond(self, address):
        self.dropped.append(address)

    def reset_adapter(self, address):
        self.resets.append(address)
        if self.reset_error is not None:
            raise self.reset_error


def make_services(**overrides):
    """A Services bundle of fakes (real preset + encoder); override any field."""
    preset = get_preset()
    fields = {
        "preset": preset, "encoder": StripEncoder(preset), "storage": FakeStorage(),
        "link": FakeLink(), "scanner": FakeScanner(), "ipc_server": None,
        "ipc_client": FakeIpcClient(), "autostart": FakeAutostart(),
        "process": FakeProcessControl(),
    }
    fields.update(overrides)
    return Services(**fields)
