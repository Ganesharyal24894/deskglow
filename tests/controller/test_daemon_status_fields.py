"""`status` fields the desktop app reads: colour, name, live mode readings."""
import asyncio

import pytest
from daemon_support import make_daemon, quiesce
from fakes import FakeStorage

from deskglow.controller import lifecycle
from deskglow.controller.modes.base import ModeContext


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


def fake_ctx(d, **telemetry):
    ctx = ModeContext(d.device, d.state, lambda _m: None)
    ctx.telemetry.update(telemetry)
    d.mode_ctx = ctx
    return ctx


async def test_solid_reports_its_colour_as_hex_and_the_settings():
    d = make_daemon(storage=FakeStorage({"name": "MELK-OA10"}))
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 180, 110]}})
    s = await d.handle({"cmd": "status"})
    assert s["color"] == "#FFB46E" and s["last_solid"] == "#FFB46E"
    assert s["name"] == "Desk strip" and s["device_name"] == "MELK-OA10"
    assert s["favourites"][0] == "#FFB46E" and s["rssi"] is None
    assert s["args"] == {"rgb": [255, 180, 110]}
    for key in ("brightness", "sunset_on", "audio_sensitivity", "hotkey_on", "tray_on",
                "theme", "focus_timer"):
        assert s[key] == d.state[key]
    assert s["screen"] is None and s["audio_level"] is None and s["focus"] is None
    await quiesce(d)


@pytest.mark.parametrize("mode,args", [("off", {}), ("pattern", {"name": "fade-red"})])
async def test_off_and_hardware_effects_have_no_colour(mode, args):
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": mode, "args": args})
    fake_ctx(d).shown = (1, 2, 3)
    assert (await d.handle({"cmd": "status"}))["color"] is None
    await quiesce(d)


async def test_a_live_mode_reports_what_it_last_showed():
    d = make_daemon()
    d.mode_name = "calm"
    fake_ctx(d).shown = (90, 140, 170)
    assert (await d.handle({"cmd": "status"}))["color"] == "#5A8CAA"


async def test_screen_mode_reports_live_colour_and_fps():
    d = make_daemon()
    d.mode_name = "screen"
    fake_ctx(d, screen_color=(74, 123, 255), screen_fps=14.96)
    s = await d.handle({"cmd": "status"})
    assert s["screen"] == {"color": "#4A7BFF", "fps": 15.0}
    d.mode_name = "calm"
    assert (await d.handle({"cmd": "status"}))["screen"] is None


async def test_audio_mode_reports_its_level():
    d = make_daemon()
    d.mode_name = "audio"
    fake_ctx(d, audio_level=0.42424)
    assert (await d.handle({"cmd": "status"}))["audio_level"] == 0.424


async def test_pomodoro_reports_its_timer():
    d = make_daemon()
    d.mode_name = "pomodoro"
    timer = {"phase": "focus", "remaining": 1122.0, "total": 1500.0, "round": 2,
             "rounds": 4, "paused": False}
    fake_ctx(d, focus=timer)
    assert (await d.handle({"cmd": "status"}))["focus"] == timer


async def test_sunset_availability_follows_the_location_service():
    d = make_daemon()
    assert (await d.handle({"cmd": "status"}))["sunset_available"] is False
    d.sunset._location = lambda: (51.5, -0.1)
    assert (await d.handle({"cmd": "status"}))["sunset_available"] is True


async def test_the_running_mode_publishes_its_context_for_status():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    for _ in range(50):
        if d.mode_ctx is not None and d.mode_ctx.shown:
            break
        await asyncio.sleep(0.01)
    assert (await d.handle({"cmd": "status"}))["color"] is not None
    await d.handle({"cmd": "off"})
    assert d.mode_ctx is None
    await quiesce(d)
