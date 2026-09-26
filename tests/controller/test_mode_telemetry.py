"""What modes publish for `status` (shown colour, screen/audio/focus readings)
and the user brightness level applied under the ceiling."""
import asyncio

import pytest
import screen_mode_support as sms
from audio_mode_support import QUIET
from audio_mode_support import install as install_audio
from mode_clock import drive, install

from deskglow.controller.modes import pomodoro as pom_mod
from deskglow.controller.modes.audio import GAIN, Audio, gain_for
from deskglow.controller.modes.pomodoro import FOCUS_COLOR, Pomodoro


async def test_brightness_scales_under_the_ceiling(make_ctx):
    ctx = make_ctx(state={"max_brightness": 50, "brightness": 50})
    await ctx.set(200, 100, 40)
    assert ctx.device.colors == [(50, 25, 10)]
    assert ctx.level() == 0.25


async def test_shown_is_the_colour_before_scaling(make_ctx):
    ctx = make_ctx(state={"max_brightness": 10})
    await ctx.set(255, 180, 110)
    assert ctx.shown == (255, 180, 110)


async def test_screen_mode_publishes_colour_and_fps(monkeypatch, make_ctx):
    env = sms.install(monkeypatch)
    env["sampler"].color = (74, 123, 255)
    ctx = sms.ctx_for(make_ctx, env)
    await sms.drive(ctx, lambda c: "screen_fps" in c.telemetry)
    assert ctx.telemetry["screen_fps"] > 0
    r, g, b = ctx.telemetry["screen_color"]
    assert b > r and b > g


@pytest.mark.parametrize("sens,gain", [(60, GAIN), (30, GAIN / 2), (100, GAIN * 100 / 60),
                                       (0, GAIN / 60), ("junk", GAIN), (None, GAIN)])
def test_sensitivity_maps_to_gain(sens, gain):
    assert gain_for(sens) == pytest.approx(gain)


async def test_audio_sensitivity_changes_the_level_and_is_published(monkeypatch, make_ctx):
    h = install_audio(monkeypatch, make_ctx)
    low = await h.run(Audio(rgb=[255, 255, 255]), [QUIET], state={"audio_sensitivity": 10})
    high = await h.run(Audio(rgb=[255, 255, 255]), [QUIET], state={"audio_sensitivity": 100})
    assert high.telemetry["audio_level"] > low.telemetry["audio_level"] > 0
    assert sum(high.device.colors[0]) > sum(low.device.colors[0])


async def test_pomodoro_publishes_phase_round_and_remaining(make_ctx, monkeypatch):
    install(monkeypatch, pom_mod)
    ctx = make_ctx()
    seen = []

    def until(c):
        f = c.telemetry.get("focus")
        if f:
            seen.append(dict(f))
        return f is not None and f["phase"] == "done"

    await drive(Pomodoro(work=1, brk=1, rounds=2), ctx, until)
    phases = [(s["phase"], s["round"]) for s in seen]
    assert ("focus", 1) in phases and ("break", 1) in phases and ("focus", 2) in phases
    assert all(s["rounds"] == 2 for s in seen)
    focus1 = [s["remaining"] for s in seen if s["phase"] == "focus" and s["round"] == 1]
    assert focus1[0] == 60.0 and min(focus1) < 0.1
    assert focus1 == sorted(focus1, reverse=True), "remaining time only counts down"


async def test_pause_freezes_the_remaining_time(make_ctx, monkeypatch):
    shim = install(monkeypatch, pom_mod)
    ctx = make_ctx()
    ctx.controls["paused"] = True
    task = asyncio.ensure_future(Pomodoro()._phase(ctx, FOCUS_COLOR, 1.0))
    for _ in range(200):
        await asyncio.sleep(0)
    assert shim.get_event_loop().time() > 1001.0          # virtual time passed...
    assert ctx.telemetry["focus"]["remaining"] == 60.0    # ...but the timer didn't
    assert ctx.telemetry["focus"]["paused"] is True
    assert set(ctx.device.colors) == {FOCUS_COLOR}        # steady while paused
    ctx.controls["paused"] = False
    await asyncio.wait_for(task, 5)
    assert ctx.telemetry["focus"]["remaining"] == 0.0
