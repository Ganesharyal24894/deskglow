"""Shared fakes for the screen-mode tests (tests/controller/test_mode_screen_*.py).

Nothing here touches X11 or mss: the ScreenSource / FocusTracker services are
fakes, the Sampler is replaced inside deskglow.controller.modes.screen, and
sleeps advance a virtual clock instantly.
"""
import asyncio

from fakes import make_services

from deskglow.controller.modes import base as base_mod
from deskglow.controller.modes import screen as screen_mod
from deskglow.controller.modes.screen import Screen

MONITORS = {
    "HDMI-1": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    "DP-2": {"left": 1920, "top": 0, "width": 2560, "height": 1440},
}
SENTINEL_RECT = {"left": -7, "top": -7, "width": 1, "height": 1}


class _VirtualAsyncio:
    """`asyncio` stand-in whose sleeps return at once (recording the delay)."""

    def __init__(self):
        self.sleeps = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def sleep(self, delay, result=None):
        self.sleeps.append(delay)
        await asyncio.sleep(0)
        return result


class FakeSampler:
    def __init__(self, color=(64, 64, 64), fail_times=0, fail_with=None):
        self.color = color
        self.fail_times = fail_times
        self.fail_with = fail_with or RuntimeError("XGetImage failed")
        self.calls = []          # [(rect, style), ...]

    async def sample(self, rect, style="average"):
        self.calls.append((rect, style))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_with
        return self.color


class FakeSource:
    """ScreenSource whose monitors() walks a list of results, then repeats the last."""

    def __init__(self, monitors_seq):
        self.monitors_seq = monitors_seq
        self.get_calls = 0
        self.closed = 0

    async def monitors(self):
        self.get_calls += 1
        seq = self.monitors_seq
        return seq[min(self.get_calls, len(seq)) - 1]

    async def grab(self, rect):
        raise AssertionError("the Sampler is faked; grab must not be reached")

    def close(self):
        self.closed += 1


class FakeFocus:
    def __init__(self, point=(2000, 500)):
        self.point = point
        self.calls = 0
        self.closed = 0

    def center(self):
        self.calls += 1
        return self.point

    def close(self):
        self.closed += 1


def install(monkeypatch):
    """Install fakes; returns a state dict the tests poke and inspect."""
    shim = _VirtualAsyncio()
    monkeypatch.setattr(screen_mod, "asyncio", shim)
    monkeypatch.setattr(base_mod, "asyncio", _VirtualAsyncio())
    state = {"sampler": FakeSampler(), "focus": FakeFocus(),
             "monitors": [dict(MONITORS)], "picked": [], "bounded": [],
             "sleeps": shim.sleeps, "sources": []}

    def pick_monitor(monitors, point):
        state["picked"].append((monitors, point))
        return SENTINEL_RECT

    def bounding_rect(monitors):
        state["bounded"].append(monitors)
        return SENTINEL_RECT

    monkeypatch.setattr(screen_mod, "pick_monitor", pick_monitor)
    monkeypatch.setattr(screen_mod, "bounding_rect", bounding_rect)
    monkeypatch.setattr(screen_mod, "Sampler", lambda source: state["sampler"])

    def open_source():
        src = FakeSource(state["monitors"])
        state["sources"].append(src)
        return src

    state["services"] = make_services(screen=open_source, focus=lambda: state["focus"])
    return state


def ctx_for(make_ctx, env, state=None):
    return make_ctx(state=state, services=env["services"])


async def drive(ctx, until, max_ticks=5000):
    """Step the mode tick by tick until `until(ctx)` holds, then cancel it."""
    task = asyncio.ensure_future(Screen().run(ctx))
    try:
        for _ in range(max_ticks):
            await asyncio.sleep(0)
            if task.done():
                await task
                break
            if until(ctx):
                break
        else:
            raise AssertionError(
                f"mode never reached the expected state within {max_ticks} ticks")
    finally:
        task.cancel()
        try:
            await task
        except BaseException:
            pass


def settles_on(expected):
    return lambda c: bool(c.device.colors) and c.device.colors[-1] == expected
