"""Solid mode: ease to the requested colour, then hold exactly that colour."""
import asyncio

import pytest
from mode_clock import drive, install

from deskglow.controller.modes import solid as solid_mod
from deskglow.controller.modes.solid import Solid


@pytest.fixture
def instant(monkeypatch):
    """Sleeps return immediately (recorded), so the 0.6s fade and 2s keepalive
    cost no wall-clock time; base.py's outage back-off is instant too."""
    return install(monkeypatch, solid_mod)


async def test_fades_up_before_holding_the_target(make_ctx, instant):
    """The strip eases into the colour instead of snapping to it."""
    ctx = make_ctx()
    await drive(Solid([255, 180, 110]), ctx, lambda c: len(c.device.colors) >= 45)
    first = ctx.device.colors[0]
    assert first != (255, 180, 110)
    assert sum(first) < sum((255, 180, 110))


async def test_fade_moves_monotonically_toward_the_target(make_ctx, instant):
    """No overshoot or flicker on the way in."""
    ctx = make_ctx()
    await drive(Solid([255, 180, 110]), ctx, lambda c: len(c.device.colors) >= 30)
    fade = ctx.device.colors[:30]
    for prev, cur in zip(fade, fade[1:], strict=False):
        assert cur[0] >= prev[0] and cur[1] >= prev[1] and cur[2] >= prev[2]
        assert cur[0] <= 255 and cur[1] <= 180 and cur[2] <= 110


async def test_final_held_colour_is_exactly_the_requested_rgb(make_ctx, instant):
    """The whole point of solid mode: the colour you asked for, precisely."""
    ctx = make_ctx()
    await drive(Solid([255, 180, 110]), ctx, lambda c: len(c.device.colors) >= 45)
    assert ctx.device.colors[-1] == (255, 180, 110)
    assert set(ctx.device.colors[-10:]) == {(255, 180, 110)}


@pytest.mark.parametrize("rgb", [(0, 0, 0), (1, 2, 3), (255, 255, 255), (7, 250, 33)])
async def test_any_colour_is_held_exactly(make_ctx, instant, rgb):
    ctx = make_ctx()
    await drive(Solid(list(rgb)), ctx, lambda c: len(c.device.colors) >= 45)
    assert ctx.device.colors[-1] == rgb


async def test_keeps_re_asserting_the_colour_as_a_keepalive(make_ctx, instant):
    """The hold loop re-sends every ~2s so the BLE link never idles out."""
    ctx = make_ctx()
    await drive(Solid([10, 20, 30]), ctx, lambda c: len(c.device.colors) >= 60)
    assert ctx.device.colors[-1] == (10, 20, 30)
    assert instant.sleeps[-1] == pytest.approx(2.0)
    assert instant.sleeps.count(2.0) >= 5, "keepalive stopped re-asserting"


# ------------------------------------------------------------- coercion ----

@pytest.mark.parametrize("given,expected", [
    ([12.9, 34.2, 5.999], (12, 34, 5)),
    (["255", "0", "128"], (255, 0, 128)),
    ((10, 20, 30), (10, 20, 30)),
    ([True, 0, 1], (1, 0, 1)),
])
def test_rgb_is_coerced_to_ints(given, expected):
    """JSON from the CLI/GUI can carry floats or strings; store ints."""
    assert Solid(given).rgb == expected


async def test_coerced_colour_is_what_reaches_the_strip(make_ctx, instant):
    ctx = make_ctx()
    await drive(Solid(["12", 34.7, 5]), ctx, lambda c: len(c.device.colors) >= 45)
    assert ctx.device.colors[-1] == (12, 34, 5)


# ------------------------------------------------------------- ceiling -----

async def test_respects_the_global_brightness_ceiling(make_ctx, instant):
    """A 50% ceiling halves every channel of the held colour."""
    ctx = make_ctx(state={"max_brightness": 50})
    await drive(Solid([255, 180, 110]), ctx, lambda c: len(c.device.colors) >= 45)
    assert ctx.device.colors[-1] == (127, 90, 55)


async def test_ceiling_of_zero_holds_black(make_ctx, instant):
    ctx = make_ctx(state={"max_brightness": 0})
    await drive(Solid([255, 180, 110]), ctx, lambda c: len(c.device.colors) >= 45)
    assert set(ctx.device.colors) == {(0, 0, 0)}


async def test_a_device_outage_does_not_kill_solid_mode(make_ctx, instant):
    """The mode keeps looping through a BLE outage and resumes on recovery."""
    ctx = make_ctx()
    ctx.device.fail_with = OSError("gone")
    dev = ctx.device

    async def recover():
        for _ in range(200):
            await asyncio.sleep(0)
        dev.fail_with = None

    helper = asyncio.ensure_future(recover())
    try:
        await drive(Solid([9, 9, 9]), ctx, lambda c: len(c.device.colors) >= 5)
    finally:
        helper.cancel()
    assert ctx.device.colors[-1] == (9, 9, 9)
    assert any("strip unreachable" in line for line in ctx.logs)


def test_describe_names_the_colour():
    assert Solid([1, 2, 3]).describe() == "solid (1, 2, 3)"
    assert Solid([1, 2, 3]).name == "solid"


async def test_switching_solid_colours_does_not_dip_through_black(make_ctx):
    """Solid mode eases into its colour, but it must ease from the colour that is
    actually lit — starting every fade at black makes the strip blink off for
    ~0.6s each time you pick a new colour."""
    import contextlib

    ctx = make_ctx()
    # the strip is currently lit bright red
    await ctx.set(255, 0, 0)
    ctx.device.last_rgb = (255, 0, 0)
    ctx.device.colors.clear()

    task = asyncio.ensure_future(Solid([0, 0, 255]).run(ctx))
    try:
        for _ in range(200):
            await asyncio.sleep(0)
            if len(ctx.device.colors) >= 10:
                break
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    assert ctx.device.colors, "solid mode wrote nothing"
    # both the old and the new colour have total brightness 255; a fade between
    # them should stay in that neighbourhood, not collapse toward zero
    darkest = min(sum(c) for c in ctx.device.colors)
    assert darkest > 150, (
        f"fade dipped to {darkest}/255 total brightness - the strip visibly "
        f"blinks off between colours (first frames: {ctx.device.colors[:4]})")
