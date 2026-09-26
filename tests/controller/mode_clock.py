"""Virtual-time helpers for driving forever-looping modes in tests.

`install(monkeypatch, module)` replaces the `asyncio` a mode module sees with a
shim whose sleeps return immediately (recording the delay) and advance a
virtual `loop.time()`. The mode base module gets its own shim too, so outage
back-off sleeps are instant. `drive()` steps a mode tick by tick until a
predicate holds, then cancels it.
"""
import asyncio

from deskglow.controller.modes import base as base_mod


class VirtualLoop:
    def __init__(self, now=1000.0):
        self.now = now

    def time(self):
        return self.now


class VirtualAsyncio:
    """`asyncio` stand-in: instant sleeps that advance a virtual clock."""

    def __init__(self, start=1000.0):
        self._loop = VirtualLoop(start)
        self.sleeps = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    def get_event_loop(self):
        return self._loop

    async def sleep(self, delay, result=None):
        self.sleeps.append(delay)
        self._loop.now += max(0.0, float(delay or 0.0))
        await asyncio.sleep(0)
        return result


def install(monkeypatch, module):
    """Shim `module.asyncio` (returned) and the base module's asyncio."""
    shim = VirtualAsyncio()
    monkeypatch.setattr(module, "asyncio", shim)
    monkeypatch.setattr(base_mod, "asyncio", VirtualAsyncio())
    return shim


async def drive(mode, ctx, until, max_ticks=200000):
    """Run `mode` until `until(ctx)` holds (bounded in ticks), then cancel it."""
    task = asyncio.ensure_future(mode.run(ctx))
    try:
        for _ in range(max_ticks):
            await asyncio.sleep(0)
            if task.done():
                await task
                break
            if until(ctx):
                break
        else:
            raise AssertionError("mode never reached the expected state")
    finally:
        task.cancel()
        try:
            await task
        except BaseException:
            pass
