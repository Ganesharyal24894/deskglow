"""ModeContext: BLE-outage guarding and supersession.

ModeContext is the only thing every mode touches, so its contract matters:
set()/raw() must never raise on a device error (a mode that dies takes the
strip with it) and must never busy-loop while the strip is unreachable.
"""
import asyncio

import pytest
from fakes import FakeDevice

from deskglow.controller.modes import base as base_mod
from deskglow.controller.modes.base import ModeContext


class _RecordingAsyncio:
    """Drop-in for the `asyncio` module inside base.py.

    Sleeps are recorded and return immediately, so a back-off schedule can be
    asserted without spending the wall-clock time it describes.
    """

    def __init__(self):
        self.sleeps = []

    def __getattr__(self, name):          # CancelledError, etc.
        return getattr(asyncio, name)

    async def sleep(self, delay, result=None):
        self.sleeps.append(delay)
        await asyncio.sleep(0)
        return result


@pytest.fixture
def clock(monkeypatch):
    shim = _RecordingAsyncio()
    monkeypatch.setattr(base_mod, "asyncio", shim)
    return shim


# --------------------------------------------------------- outage guarding --

async def test_set_swallows_device_errors_instead_of_raising(make_ctx, clock):
    """A BLE write blowing up must not kill the mode loop that called set()."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("le-connection-abort-by-local")
    await ctx.set(1, 2, 3)          # must not raise
    assert ctx.device.colors == []


async def test_raw_swallows_device_errors_instead_of_raising(make_ctx, clock):
    ctx = make_ctx()
    ctx.device.fail_with = OSError("boom")
    await ctx.raw(b"\x7e")          # must not raise
    assert ctx.device.frames == []


async def test_first_failure_logs_strip_unreachable(make_ctx, clock):
    """The user needs one clear line when the strip drops off."""
    ctx = make_ctx()
    ctx.device.fail_with = TimeoutError("gone")
    await ctx.set(1, 2, 3)
    assert len(ctx.logs) == 1
    assert "strip unreachable" in ctx.logs[0]
    assert "TimeoutError" in ctx.logs[0]


async def test_repeated_failures_do_not_spam_the_log(make_ctx, clock):
    """Only the 1st and every 50th failure is logged, so a long outage is quiet."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    for _ in range(60):
        await ctx.set(1, 2, 3)
    assert len(ctx.logs) == 2, ctx.logs
    assert all("strip unreachable" in line for line in ctx.logs)


async def test_recovery_logs_strip_reachable_again(make_ctx, clock):
    """Coming back must be announced, and only when there was an outage."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    await ctx.set(1, 2, 3)
    ctx.device.fail_with = None
    await ctx.set(4, 5, 6)
    assert ctx.logs[-1] == "strip reachable again"
    assert ctx.device.colors == [(4, 5, 6)]


async def test_a_clean_run_never_logs_anything(make_ctx, clock):
    """No outage => no "reachable again" noise on every single write."""
    ctx = make_ctx()
    for _ in range(5):
        await ctx.set(1, 2, 3)
    assert ctx.logs == []


async def test_failure_counter_resets_after_recovery(make_ctx, clock):
    """A second outage must start its back-off from scratch, not where it left off."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    for _ in range(5):
        await ctx.set(1, 2, 3)
    ctx.device.fail_with = None
    await ctx.set(1, 2, 3)
    assert ctx._fails == 0
    clock.sleeps.clear()
    ctx.logs.clear()
    ctx.device.fail_with = OSError("gone again")
    await ctx.set(1, 2, 3)
    assert clock.sleeps == [pytest.approx(0.2)], "back-off did not restart"
    assert "strip unreachable" in ctx.logs[0], "second outage was not announced"


async def test_failures_back_off_instead_of_busy_looping(make_ctx, clock):
    """Each consecutive failure waits longer, capped so recovery stays snappy."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    for _ in range(15):
        await ctx.set(1, 2, 3)
    assert len(clock.sleeps) == 15
    assert all(s > 0 for s in clock.sleeps), "a failing write must not spin"
    assert clock.sleeps[0] < clock.sleeps[1] < clock.sleeps[2]
    assert max(clock.sleeps) <= 2.0
    assert clock.sleeps[-1] == pytest.approx(2.0), "back-off should reach its cap"


async def test_successful_writes_do_not_sleep(make_ctx, clock):
    """The guard only throttles on failure; the happy path stays at full rate."""
    ctx = make_ctx()
    for _ in range(5):
        await ctx.set(1, 2, 3)
    assert clock.sleeps == []


# ------------------------------------------------------------ supersession --

async def test_superseded_context_refuses_to_set(make_ctx):
    """A mode that outlived its cancel() must not fight the new mode's colour."""
    ctx = make_ctx(is_current=lambda: False)
    with pytest.raises(asyncio.CancelledError):
        await ctx.set(1, 2, 3)
    assert ctx.device.colors == []


async def test_superseded_context_refuses_to_send_raw_frames(make_ctx):
    ctx = make_ctx(is_current=lambda: False)
    with pytest.raises(asyncio.CancelledError):
        await ctx.raw(b"\x7e\x00")
    assert ctx.device.frames == []


async def test_supersession_is_rechecked_on_every_write(make_ctx):
    """The generation can flip at any time, not just before the mode starts."""
    current = {"ok": True}
    ctx = make_ctx(is_current=lambda: current["ok"])
    await ctx.set(1, 2, 3)
    current["ok"] = False
    with pytest.raises(asyncio.CancelledError):
        await ctx.set(9, 9, 9)
    assert ctx.device.colors == [(1, 2, 3)]


async def test_sleep_checks_supersession_after_sleeping(make_ctx, clock):
    """Most of a mode's life is spent in sleep(): waking up superseded must
    cancel it right there, before it writes the next frame."""
    current = {"ok": True}
    ctx = make_ctx(is_current=lambda: current["ok"])

    real_sleep = clock.sleep

    async def flip(delay, result=None):
        current["ok"] = False           # superseded *while* sleeping
        return await real_sleep(delay, result)

    clock.sleep = flip
    with pytest.raises(asyncio.CancelledError):
        await ctx.sleep(0.05)
    assert clock.sleeps == [0.05], "supersession must be checked after the sleep"


async def test_sleep_returns_normally_while_still_current(make_ctx, clock):
    ctx = make_ctx()
    await ctx.sleep(0.25)
    assert clock.sleeps == [0.25]


async def test_default_is_current_treats_the_mode_as_live(make_ctx):
    """Contexts built without an is_current callback always write."""
    ctx = ModeContext(FakeDevice(), {"max_brightness": 100}, lambda _m: None)
    await ctx.set(7, 8, 9)
    assert ctx.device.colors == [(7, 8, 9)]
