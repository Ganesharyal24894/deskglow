"""`config` for the app's settings, restarts that apply them, and focus_pause."""
import asyncio

import pytest
from daemon_support import make_daemon, quiesce

from deskglow.controller import lifecycle
from deskglow.controller.modes.base import ModeContext


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


@pytest.mark.parametrize("key,value", [
    ("strip_name", "Shelf"), ("sunset_on", True), ("audio_sensitivity", 90),
    ("hotkey_on", True), ("tray_on", False), ("theme", "dark"), ("brightness", 40),
    ("favourites", ["#000000"]), ("focus_timer", {"work": 50, "break": 10, "rounds": 2}),
])
async def test_app_settings_are_stored_and_persisted(key, value):
    d = make_daemon()
    resp = await d.handle({"cmd": "config", "key": key, "value": value})
    assert resp == {"ok": True, key: value}
    assert d.services.storage.state[key] == value


async def test_invalid_app_setting_is_rejected_and_not_stored():
    d = make_daemon()
    resp = await d.handle({"cmd": "config", "key": "theme", "value": "neon"})
    assert resp["ok"] is False
    assert d.state["theme"] == "system"


async def test_brightness_change_restarts_a_solid_mode_so_it_shows_at_once():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [200, 100, 0]}})
    first = d.mode_task
    await d.handle({"cmd": "config", "key": "brightness", "value": 50})
    assert d.mode_task is not first and d.mode_name == "solid"
    await asyncio.sleep(0.8)
    assert d.device.colors[-1] == (100, 50, 0)
    await quiesce(d)


async def test_unchanged_value_or_unaffected_mode_does_not_restart():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    first = d.mode_task
    await d.handle({"cmd": "config", "key": "brightness", "value": 50})
    await d.handle({"cmd": "config", "key": "screen_style", "value": "edge"})
    assert d.mode_task is first
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [1, 1, 1]}})
    second = d.mode_task
    await d.handle({"cmd": "config", "key": "brightness", "value": 50})   # same value
    assert d.mode_task is second
    await quiesce(d)


async def test_screen_setting_change_restarts_screen_mode(monkeypatch):
    d = make_daemon()
    d.mode_name, d.mode_args = "screen", {}
    calls = []

    async def fake_set_mode(name, args):
        calls.append((name, args))

    monkeypatch.setattr(d, "set_mode", fake_set_mode)
    await d.handle({"cmd": "config", "key": "screen_monitor", "value": "DP-1"})
    assert calls == [("screen", {})]


async def test_focus_pause_reaches_the_running_timer():
    d = make_daemon()
    d.mode_name = "pomodoro"
    d.mode_ctx = ModeContext(d.device, d.state, lambda _m: None)
    assert await d.handle({"cmd": "focus_pause", "paused": True}) == {"ok": True, "paused": True}
    assert d.mode_ctx.controls["paused"] is True
    await d.handle({"cmd": "focus_pause", "paused": False})
    assert d.mode_ctx.controls["paused"] is False
    assert (await d.handle({"cmd": "focus_pause", "paused": "yes"}))["ok"] is False


async def test_focus_pause_without_a_timer_is_an_error():
    d = make_daemon()
    resp = await d.handle({"cmd": "focus_pause", "paused": True})
    assert resp == {"ok": False, "error": "no focus timer is running"}


async def test_focus_pause_refuses_other_modes_even_with_a_context():
    d = make_daemon()
    d.mode_name = "calm"
    d.mode_ctx = ModeContext(d.device, d.state, lambda _m: None)
    assert (await d.handle({"cmd": "focus_pause", "paused": True}))["ok"] is False
    assert "paused" not in d.mode_ctx.controls
