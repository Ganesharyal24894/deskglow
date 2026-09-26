"""Fixtures for the Device tests: a fake clock and the fake BLE world.

The modules' clock and sleeps are replaced so the rate limiter, keepalive and
connect backoff run instantly and deterministically.
"""
import asyncio
import time as _time

import pytest

from deskglow.controller import connect, device
from device_harness import FakeBle


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, start=1000.0):
        self.now = start
        self.sleeps = []

    def advance(self, dt):
        self.now += dt


class _FakeTimeModule:
    """`time` as the modules see it: real, except monotonic() is our clock."""

    def __init__(self, clock):
        self._clock = clock

    def monotonic(self):
        return self._clock.now

    def __getattr__(self, name):
        return getattr(_time, name)


class _FakeAsyncioModule:
    """`asyncio` as the modules see it: sleep() is instant and advances the clock."""

    def __init__(self, clock):
        self._clock = clock

    async def sleep(self, delay, result=None):
        self._clock.sleeps.append(delay)
        self._clock.advance(max(0.0, delay))
        await asyncio.sleep(0)
        return result

    def __getattr__(self, name):
        return getattr(asyncio, name)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    """Freeze the device/connect clock and make their sleeps instant."""
    c = FakeClock()
    for mod in (device, connect):
        monkeypatch.setattr(mod, "time", _FakeTimeModule(c), raising=False)
        monkeypatch.setattr(mod, "asyncio", _FakeAsyncioModule(c))
    return c


@pytest.fixture
def logs():
    return []


@pytest.fixture
def ble(monkeypatch, clock):
    monkeypatch.setattr(connect, "SCAN_TIMEOUT", 0.02)
    return FakeBle(clock)
