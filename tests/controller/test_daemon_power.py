"""Daemon `on` / `toggle`: turning back on restores what was lit before `off`."""
import pytest
from daemon_support import make_daemon, quiesce

from deskglow.controller import lifecycle


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


async def test_on_with_no_history_lights_warm_white():
    d = make_daemon()
    resp = await d.handle({"cmd": "on"})
    assert resp["ok"] and d.mode_name == "solid"
    assert d.mode_args == {"rgb": [255, 180, 110]}
    await quiesce(d)


async def test_on_resumes_the_mode_that_off_interrupted():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "pattern", "args": {"name": "blink-red", "speed": 9}})
    await d.handle({"cmd": "off"})
    assert d.mode_name == "off"
    await d.handle({"cmd": "on"})
    assert d.mode_name == "pattern"
    assert d.mode_args == {"name": "blink-red", "speed": 9}
    await quiesce(d)


async def test_resume_survives_a_restart_via_persisted_state():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    await d.handle({"cmd": "off"})
    await quiesce(d)
    d2 = make_daemon(storage=d.services.storage)
    await d2.handle({"cmd": "on"})
    assert d2.mode_name == "calm"
    await quiesce(d2)


async def test_last_solid_colour_is_remembered_and_used_by_turn_on_solid():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [1, 2, 300]}})
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    assert d.state["last_solid"] == [1, 2, 255]
    await d.turn_on_solid()
    assert d.mode_args == {"rgb": [1, 2, 255]}
    await quiesce(d)


@pytest.mark.parametrize("bad", ["red", [1, 2], [True, 0, 0], None])
async def test_a_malformed_solid_colour_is_not_remembered(bad):
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": bad}})
    assert d.state["last_solid"] == [255, 180, 110]
    await quiesce(d)


async def test_toggle_turns_off_then_back_on():
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [9, 9, 9]}})
    r1 = await d.handle({"cmd": "toggle"})
    assert r1["on"] is False and d.mode_name == "off"
    r2 = await d.handle({"cmd": "toggle"})
    assert r2["on"] is True and d.mode_args == {"rgb": [9, 9, 9]}
    await quiesce(d)


async def test_on_falls_back_to_solid_when_the_resumed_mode_cannot_start():
    d = make_daemon()
    d.state["resume"] = {"mode": "no-such-mode", "args": {}}
    await d.handle({"cmd": "on"})
    assert d.mode_name == "solid"
    await quiesce(d)
