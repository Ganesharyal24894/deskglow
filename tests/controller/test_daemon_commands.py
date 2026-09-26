"""Daemon.handle(): the command surface a client sees (ping/status/set_mode/...)."""

import pytest
from daemon_support import make_daemon, quiesce

from deskglow.controller import lifecycle
from deskglow.controller.settings import SettingsStore


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    """Never wait 30 real seconds for the idle-disconnect timer."""
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


def saved_state(d):
    return SettingsStore(d.services.storage).load_state()


async def test_ping_returns_pong():
    """`ping` is the liveness probe the CLI and a second daemon rely on."""
    d = make_daemon()
    assert await d.handle({"cmd": "ping"}) == {"ok": True, "pong": True}


async def test_status_reports_every_field():
    """`status` mirrors the daemon's live mode plus the persisted settings."""
    d = make_daemon(address="11:22:33:44:55:66")
    d.state["screen_monitor"] = "HDMI-0"
    d.state["screen_style"] = "edge"
    d.state["max_brightness"] = 70
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [1, 2, 3]}})

    resp = await d.handle({"cmd": "status"})
    assert {k: resp[k] for k in ("ok", "mode", "desc", "connected", "configured", "address",
                                 "screen_monitor", "screen_style", "max_brightness")} == {
        "ok": True,
        "mode": "solid",
        "desc": "solid (1, 2, 3)",
        "connected": True,
        "configured": True,
        "address": "11:22:33:44:55:66",
        "screen_monitor": "HDMI-0",
        "screen_style": "edge",
        "max_brightness": 70,
    }
    await quiesce(d)


async def test_status_reports_unconfigured_strip():
    """With no MAC saved, `configured` must be False so a client can say so."""
    d = make_daemon()
    d.device.address = None
    d.device.connected = False
    resp = await d.handle({"cmd": "status"})
    assert resp["configured"] is False
    assert resp["address"] is None
    assert resp["connected"] is False


@pytest.mark.parametrize("name,args,desc", [
    ("solid", {"rgb": [10, 20, 30]}, "solid (10, 20, 30)"),
    ("screen", {}, "screen"),
    ("calm", {}, "calm"),
    ("pattern", {"name": "blink-red", "speed": 30}, "pattern:blink-red@30"),
    ("circadian", {}, "circadian"),
    ("pomodoro", {"work": 25, "break": 5, "rounds": 4}, None),
    ("audio", {"source": "mic"}, None),
])
async def test_set_mode_accepts_every_registered_mode(name, args, desc):
    """Every name in the mode registry can be started through `set_mode`."""
    d = make_daemon()
    resp = await d.handle({"cmd": "set_mode", "mode": name, "args": args})
    await quiesce(d)          # cancel before the mode body ever runs
    assert resp["ok"] is True
    assert resp["mode"] == name
    if desc is not None:
        assert resp["desc"] == desc
    assert resp["desc"] and not resp["desc"].startswith("off")


async def test_off_command_powers_down():
    """`off` stops the mode and pulls the strip's power line down."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    resp = await d.handle({"cmd": "off"})
    assert resp == {"ok": True}
    assert d.mode_name == "off"
    assert d.device.power_calls[-1] is False
    await quiesce(d)


async def test_reset_forces_known_good_solid_white():
    """`reset` re-asserts a known-good state, clears the ceiling, holds white."""
    d = make_daemon()
    d.state["max_brightness"] = 20
    resp = await d.handle({"cmd": "reset"})
    assert resp == {"ok": True, "reset": True}
    assert b"RESET" in d.device.frames
    assert d.state["max_brightness"] == 100
    assert saved_state(d)["max_brightness"] == 100
    assert d.mode_name == "solid"
    assert d.mode_desc == "solid (255, 255, 255)"
    await quiesce(d)


async def test_reset_reports_an_unreachable_strip():
    """A BLE failure during `reset` is reported, not raised at the client."""
    d = make_daemon()
    d.device.fail_with = ConnectionError("no link")
    resp = await d.handle({"cmd": "reset"})
    assert resp["ok"] is False
    assert "strip unreachable" in resp["error"]
    await quiesce(d)


async def test_reload_restarts_the_current_mode_and_clears_backoff():
    """`reload` picks up a freshly-configured address without changing mode."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    resp = await d.handle({"cmd": "reload"})
    assert resp == {"ok": True, "configured": True}
    assert d.device.backoff_resets == 1
    assert d.mode_name == "calm"
    await quiesce(d)


async def test_shutdown_sets_the_stop_event():
    """`shutdown` is what makes serve() fall out of its wait loop."""
    d = make_daemon()
    assert await d.handle({"cmd": "shutdown"}) == {"ok": True, "shutting_down": True}
    assert d._stop.is_set()


async def test_request_stop_sets_the_stop_event():
    """request_stop() is the signal-handler route to the same shutdown."""
    d = make_daemon()
    d.request_stop()
    assert d._stop.is_set()


async def test_unknown_command_is_reported_helpfully():
    """A typo'd command gets ok:False and the offending name echoed back."""
    d = make_daemon()
    resp = await d.handle({"cmd": "flibble"})
    assert resp["ok"] is False
    assert "flibble" in resp["error"]
    assert "unknown cmd" in resp["error"]


async def test_missing_command_is_reported_helpfully():
    """A request with no cmd at all must not raise inside the daemon."""
    d = make_daemon()
    resp = await d.handle({})
    assert resp["ok"] is False
    assert resp["error"]
