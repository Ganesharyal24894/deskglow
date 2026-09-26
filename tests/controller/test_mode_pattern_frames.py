"""Patterns mode on the wire: brightness, effect and speed frames, re-asserted.

These are raw protocol frames sent to the controller, so the tests assert the
exact bytes -- a wrong effect id silently plays the wrong animation.
"""
import asyncio

import pytest
from mode_clock import drive, install

from deskglow.controller.modes import patterns as pat_mod
from deskglow.controller.modes.patterns import Patterns


def _brightness_frame(pct):
    return bytes([0x7E, 0x00, 0x01, pct, 0x00, 0x00, 0x00, 0x00, 0xEF])


def _effect_frame(eid):
    return bytes([0x7E, 0x00, 0x03, eid, 0x03, 0x00, 0x00, 0x00, 0xEF])


def _speed_frame(pct):
    return bytes([0x7E, 0x00, 0x02, pct, 0x00, 0x00, 0x00, 0x00, 0xEF])




@pytest.fixture
def instant(monkeypatch):
    return install(monkeypatch, pat_mod)


# ------------------------------------------------------------- the frames ---

async def test_sends_brightness_then_effect_then_speed(make_ctx, instant):
    """Order matters: brightness first, then the effect, then its speed."""
    ctx = make_ctx(state={"max_brightness": 100})
    await drive(Patterns("blink-white", 30), ctx,
                 lambda c: len(c.device.frames) >= 3)
    assert ctx.device.frames[:3] == [
        _brightness_frame(100),
        _effect_frame(0x9C),
        _speed_frame(30),
    ]


async def test_frames_carry_the_configured_brightness_ceiling(make_ctx, instant):
    """The ceiling reaches the hardware effect through the brightness frame."""
    ctx = make_ctx(state={"max_brightness": 35})
    await drive(Patterns("fade-colors", 50), ctx,
                 lambda c: len(c.device.frames) >= 3)
    assert ctx.device.frames[0] == _brightness_frame(35)


async def test_no_rgb_colours_are_streamed(make_ctx, instant):
    """The controller runs the effect itself; streaming colours would fight it."""
    ctx = make_ctx()
    await drive(Patterns("jump-rgb", 60), ctx, lambda c: len(c.device.frames) >= 6)
    assert ctx.device.colors == []


async def test_effect_is_re_asserted_periodically(make_ctx, instant, monkeypatch):
    """After a reconnect the strip forgets the effect, so it is re-sent."""
    monkeypatch.setattr(pat_mod, "REASSERT", 0.001)
    ctx = make_ctx()
    await drive(Patterns("fade-blue", 20), ctx, lambda c: len(c.device.frames) >= 9)
    expected = [_brightness_frame(100), _effect_frame(0x8D), _speed_frame(20)]
    assert ctx.device.frames[:9] == expected * 3
    assert instant.sleeps[:2] == [0.001, 0.001]


async def test_reassert_interval_is_the_module_constant(make_ctx, instant):
    """Default cadence is REASSERT seconds between re-sends."""
    ctx = make_ctx()
    await drive(Patterns("fade-red", 10), ctx, lambda c: len(c.device.frames) >= 6)
    assert instant.sleeps[0] == pat_mod.REASSERT


async def test_a_device_outage_does_not_kill_pattern_mode(make_ctx, instant):
    """Frames dropped during an outage are retried once the strip is back."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    dev = ctx.device

    async def recover():
        for _ in range(100):
            await asyncio.sleep(0)
        dev.fail_with = None

    helper = asyncio.ensure_future(recover())
    try:
        await drive(Patterns("fade-cyan", 50), ctx,
                     lambda c: len(c.device.frames) >= 3)
    finally:
        helper.cancel()
    assert ctx.device.frames[:3] == [
        _brightness_frame(100), _effect_frame(0x8F), _speed_frame(50)]
    assert any("strip unreachable" in line for line in ctx.logs)


def test_describe_and_name():
    m = Patterns("blink-red", 7)
    assert m.name == "pattern"
    assert m.describe() == "pattern:blink-red@7"
