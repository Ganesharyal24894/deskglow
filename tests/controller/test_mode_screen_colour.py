"""Screen mode: the sampled colour pipeline, resilience and resource cleanup."""
import asyncio

import pytest
from screen_mode_support import MONITORS, ctx_for, drive, install, settles_on

from deskglow.controller.modes.screen import Screen
from deskglow.model import color as colormod


@pytest.fixture
def env(monkeypatch):
    return install(monkeypatch)


# ------------------------------------------------------- colour pipeline ----

async def test_the_sampled_colour_reaches_the_device(make_ctx, env):
    """The screen colour must actually be written to the strip."""
    env["sampler"].color = (64, 64, 64)
    expected = colormod.gamma((64, 64, 64), 1.6)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, settles_on(expected))
    assert ctx.device.colors[-1] == expected


async def test_gamma_is_applied_to_the_sample(make_ctx, env):
    """A raw mid-grey screen would look far too dim without gamma."""
    env["sampler"].color = (64, 64, 64)
    expected = colormod.gamma((64, 64, 64), 1.6)
    assert expected != (64, 64, 64), "the test colour must be gamma-sensitive"
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, settles_on(expected))
    assert ctx.device.colors[-1][0] > 64, "gamma was not applied"


async def test_minimum_glow_floor_is_applied(make_ctx, env):
    """A saturated screen must not leave the other channels at hard zero."""
    env["sampler"].color = (255, 0, 0)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, settles_on((255, 4, 4)))
    assert ctx.device.colors[-1] == (255, 4, 4)


async def test_a_non_black_sample_never_produces_a_pure_black_write(make_ctx, env):
    """Even a near-black screen keeps a faint glow rather than switching off."""
    env["sampler"].color = (1, 1, 1)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: len(c.device.colors) >= 40)
    assert all(max(col) > 0 for col in ctx.device.colors), ctx.device.colors[:5]


async def test_a_black_screen_does_turn_the_strip_off(make_ctx, env):
    """The floor only applies to non-black samples; true black stays black."""
    env["sampler"].color = (0, 0, 0)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: len(c.device.colors) >= 20)
    assert set(ctx.device.colors) == {(0, 0, 0)}


async def test_colour_changes_are_smoothed(make_ctx, env):
    """Frame-to-frame jumps would strobe; the smoother ramps instead."""
    env["sampler"].color = (255, 255, 255)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: len(c.device.colors) >= 25)
    assert ctx.device.colors[0] != (255, 255, 255)
    for prev, cur in zip(ctx.device.colors, ctx.device.colors[1:], strict=False):
        assert all(c >= p for p, c in zip(prev, cur, strict=False))


async def test_respects_the_brightness_ceiling(make_ctx, env):
    env["sampler"].color = (255, 255, 255)
    ctx = ctx_for(make_ctx, env, state={"max_brightness": 50})
    await drive(ctx, settles_on((127, 127, 127)))
    assert ctx.device.colors[-1] == (127, 127, 127)


# -------------------------------------------------------------- resilience --

async def test_a_capture_error_is_logged_and_the_loop_survives(make_ctx, env):
    """One bad grab (screen locked, GPU hiccup) must not end screen mode."""
    env["sampler"].fail_times = 3
    env["sampler"].color = (128, 128, 128)
    expected = colormod.gamma((128, 128, 128), 1.6)
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, settles_on(expected))
    assert sum("screen capture error" in line for line in ctx.logs) == 3
    assert ctx.device.colors, "the loop stopped after the capture error"


async def test_a_capture_error_backs_off_rather_than_spinning(make_ctx, env):
    env["sampler"].fail_times = 1
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: len(c.device.colors) >= 5)
    assert 0.5 in env["sleeps"], "a failed capture must pause before retrying"


async def test_an_empty_monitor_list_retries_instead_of_crashing(make_ctx, env):
    """A systemd --user daemon can start before X is up; keep retrying."""
    env["monitors"] = [{}, {}, dict(MONITORS)]
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: len(c.device.colors) >= 5)
    assert any("no monitors/display available" in line for line in ctx.logs)
    assert any("monitors now" in line for line in ctx.logs)
    assert 3 in env["sleeps"], "an empty monitor list must pause before retrying"
    assert ctx.device.colors, "never recovered once the display appeared"


async def test_a_device_outage_does_not_kill_screen_mode(make_ctx, env):
    """A BLE hiccup is swallowed; the capture loop keeps going."""
    env["sampler"].color = (255, 255, 255)
    ctx = ctx_for(make_ctx, env)
    ctx.device.fail_with = OSError("gone")
    dev = ctx.device

    async def recover():
        for _ in range(300):
            await asyncio.sleep(0)
        dev.fail_with = None

    helper = asyncio.ensure_future(recover())
    try:
        await drive(ctx, lambda c: len(c.device.colors) >= 3)
    finally:
        helper.cancel()
    assert ctx.device.colors
    assert any("strip unreachable" in line for line in ctx.logs)


# -------------------------------------------------------------- resources ---

async def test_screen_mode_releases_its_capture_resources_when_it_stops(make_ctx, env):
    """Screen mode opens a capture handle and a focus tracker (each an X
    connection) every time it starts; both must be closed when it stops, or
    every restart leaks an X connection until the server refuses clients."""
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, lambda c: bool(c.device.colors))
    assert env["sources"][0].closed == 1, "screen mode leaked its capture handle"
    assert env["focus"].closed == 1, "screen mode leaked its focus tracker"


async def test_resources_are_released_even_when_the_first_listing_fails(make_ctx, env):
    """A failure before the loop starts must still close what was opened."""
    async def boom():
        raise RuntimeError("no display")

    ctx = ctx_for(make_ctx, env)
    real_screen = env["services"].screen

    def failing():
        src = real_screen()
        src.monitors = boom
        return src

    env["services"].screen = failing
    with pytest.raises(RuntimeError):
        await Screen().run(ctx)
    assert env["sources"][0].closed == 1
    assert env["focus"].closed == 1


def test_name():
    assert Screen().name == "screen"
    assert Screen().describe().strip()
