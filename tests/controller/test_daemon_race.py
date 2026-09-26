"""Regression test for the two-modes-at-once flicker bug.

Overlapping set_mode() calls used to each start a mode task while the loser's
task kept running unreferenced, so two mode loops drove the strip at the same
time and the colour flickered between the two. Pre-fix this reached 5 concurrent
loops; the daemon must now guarantee at most one.
"""
import asyncio

import pytest
from daemon_support import make_daemon


async def _daemon_with_tracking(latency=0.05):
    d = make_daemon(latency=latency)
    live = set()
    peak = 0
    orig_run_mode = d._run_mode

    async def instrumented(mode, gen):
        nonlocal peak
        live.add(gen)
        peak = max(peak, len(live))
        try:
            await orig_run_mode(mode, gen)
        finally:
            live.discard(gen)

    d._run_mode = instrumented
    return d, live, lambda: peak


async def test_overlapping_set_mode_never_runs_two_modes():
    d, live, peak = await _daemon_with_tracking()
    reqs = [
        {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 0, 0]}},
        {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [0, 255, 0]}},
        {"cmd": "set_mode", "mode": "calm", "args": {}},
        {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [0, 0, 255]}},
        {"cmd": "reload"},
        {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 255, 0]}},
    ]
    await asyncio.gather(*(d.handle(r) for r in reqs))
    for _ in range(20):
        await asyncio.sleep(0.02)
        assert len(live) <= 1, "more than one mode loop is driving the strip"
    assert peak() <= 1
    assert len(live) == 1, "exactly one mode should survive"
    await d._stop_mode()


async def test_reset_does_not_orphan_the_running_mode():
    d, live, peak = await _daemon_with_tracking()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    await asyncio.gather(
        d.handle({"cmd": "reset"}),
        d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [1, 2, 3]}}),
    )
    await asyncio.sleep(0.1)
    assert peak() <= 1
    assert len(live) == 1
    await d._stop_mode()


async def test_superseded_mode_context_refuses_to_write(make_ctx):
    """Even if a mode loop outlives its cancel(), it must not touch the strip."""
    current = {"ok": True}
    ctx = make_ctx(is_current=lambda: current["ok"])
    await ctx.set(10, 20, 30)
    assert ctx.device.colors == [(10, 20, 30)]
    current["ok"] = False
    with pytest.raises(asyncio.CancelledError):
        await ctx.set(99, 99, 99)
    assert ctx.device.colors == [(10, 20, 30)], "superseded mode wrote to the strip"


async def test_the_running_mode_gets_a_context_with_the_daemon_services():
    """The daemon hands each mode its services (encoder, capture factories)."""
    d = make_daemon()
    seen = []

    class Probe:
        name = "probe"

        async def run(self, ctx):
            seen.append(ctx)

    await d._run_mode(Probe(), d._gen)
    assert seen[0].services is d.services
    assert seen[0].device is d.device
    assert seen[0]._is_current()
    d._gen += 1
    assert not seen[0]._is_current(), "context must track the generation counter"
