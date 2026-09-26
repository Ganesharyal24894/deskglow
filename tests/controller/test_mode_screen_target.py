"""Screen mode: which monitor it samples, with which style, and what it logs."""
import pytest
from screen_mode_support import MONITORS, SENTINEL_RECT, ctx_for, drive, install


@pytest.fixture
def env(monkeypatch):
    return install(monkeypatch)


def _sampled(env):
    return lambda c: bool(env["sampler"].calls)


# ---------------------------------------------------------- target choice ---

async def test_focus_target_uses_the_active_window_monitor(make_ctx, env):
    """The default: follow whichever monitor the focused window is on."""
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, _sampled(env))
    assert env["picked"], "pick_monitor was never consulted"
    monitors, point = env["picked"][0]
    assert monitors == MONITORS
    assert point == (2000, 500)
    assert env["sampler"].calls[0][0] == SENTINEL_RECT
    assert env["bounded"] == []


async def test_both_target_uses_the_bounding_rect_of_all_monitors(make_ctx, env):
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_monitor": "both"})
    await drive(ctx, _sampled(env))
    assert env["bounded"] and env["bounded"][0] == MONITORS
    assert env["sampler"].calls[0][0] == SENTINEL_RECT
    assert env["picked"] == []


async def test_a_named_monitor_is_sampled_directly(make_ctx, env):
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_monitor": "DP-2"})
    await drive(ctx, _sampled(env))
    assert env["sampler"].calls[0][0] == MONITORS["DP-2"]
    assert env["picked"] == [] and env["bounded"] == []


async def test_an_unknown_monitor_name_falls_back_to_focus(make_ctx, env):
    """A monitor that got unplugged must not wedge the mode."""
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_monitor": "VGA-9"})
    await drive(ctx, _sampled(env))
    assert env["picked"], "did not fall back to focus"
    assert env["sampler"].calls[0][0] == SENTINEL_RECT


# ----------------------------------------------------------------- styles ---

@pytest.mark.parametrize("style", ["average", "vivid", "dominant", "edge"])
async def test_a_valid_style_is_passed_to_the_sampler(make_ctx, env, style):
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_style": style})
    await drive(ctx, _sampled(env))
    assert env["sampler"].calls[0][1] == style


@pytest.mark.parametrize("style", ["bogus", "", None, "VIVID", 3])
async def test_an_invalid_style_falls_back_to_vivid(make_ctx, env, style):
    """A typo in the config must not sample with an unknown style."""
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_style": style})
    await drive(ctx, _sampled(env))
    assert env["sampler"].calls[0][1] == "vivid"
    assert any("style=vivid" in line for line in ctx.logs)


async def test_default_style_is_vivid(make_ctx, env):
    ctx = ctx_for(make_ctx, env)
    await drive(ctx, _sampled(env))
    assert env["sampler"].calls[0][1] == "vivid"


async def test_startup_log_names_monitors_target_and_style(make_ctx, env):
    """One line at startup so a user can see what screen mode decided to do."""
    ctx = ctx_for(make_ctx, env, {"max_brightness": 100, "screen_monitor": "DP-2",
                                  "screen_style": "edge"})
    await drive(ctx, lambda c: bool(c.logs))
    line = ctx.logs[0]
    assert "screen-mode" in line
    assert "DP-2" in line and "edge" in line
