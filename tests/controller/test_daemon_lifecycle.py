"""Daemon mode lifecycle: one mode at a time, idle disconnect, contained crashes."""
import asyncio

import pytest
from daemon_support import BoomMode, make_daemon, quiesce

from deskglow.controller import lifecycle


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    """Never wait 30 real seconds for the idle-disconnect timer."""
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


async def test_starting_a_mode_cancels_the_previous_one():
    """Only one mode ever drives the strip: the outgoing task must be cancelled."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    first = d.mode_task
    await asyncio.sleep(0.02)          # let calm actually start
    assert not first.done()

    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [9, 9, 9]}})
    assert first.done()
    assert d.mode_task is not first
    assert not d.mode_task.done(), "the new mode's task should be running"
    await quiesce(d)


async def test_off_schedules_the_idle_disconnect():
    """Going off arms the timer that releases the radio for other BT devices."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    await d.handle({"cmd": "off"})
    assert d._idle_task is not None and not d._idle_task.done()
    assert d.mode_task is None
    await quiesce(d)


async def test_idle_disconnect_releases_the_link_when_still_off():
    """After the idle timeout with nothing running, the BLE link is dropped."""
    d = make_daemon()
    await d.handle({"cmd": "off"})
    await asyncio.sleep(0.1)
    assert d.device.disconnects == 1
    await quiesce(d)


async def test_idle_disconnect_is_cancelled_when_a_mode_starts():
    """Starting a mode inside the idle window must keep the link up."""
    d = make_daemon()
    await d.handle({"cmd": "off"})
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    await asyncio.sleep(0.1)
    assert d.device.disconnects == 0, "idle timer disconnected a live mode"
    await quiesce(d)


async def test_idle_disconnect_checks_the_mode_before_disconnecting():
    """Even if the timer fires late, it must not cut a running mode's link."""
    d = make_daemon()
    d.mode_name = "calm"
    await d._idle_then_disconnect()
    assert d.device.disconnects == 0


async def test_mode_that_raises_is_contained(monkeypatch):
    """A crashing mode must not kill the daemon; it degrades to a labelled off."""
    real_build = lifecycle.modes.build
    monkeypatch.setattr(
        lifecycle.modes, "build",
        lambda n, a, preset=None: BoomMode() if n == "boom" else real_build(n, a, preset))
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "boom", "args": {}})
    await asyncio.sleep(0.02)

    assert d.mode_name == "off"
    assert d.mode_desc == "off (after boom error)"
    # still fully responsive afterwards
    assert (await d.handle({"cmd": "ping"}))["pong"] is True
    resp = await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [1, 1, 1]}})
    assert resp["ok"] is True and resp["mode"] == "solid"
    await quiesce(d)


async def test_unknown_mode_name_leaves_a_sane_off_state():
    """An invalid mode name is refused into 'off', not left half-started."""
    d = make_daemon()
    resp = await d.handle({"cmd": "set_mode", "mode": "does-not-exist", "args": {}})
    assert resp["ok"] is True          # handled, just not started
    assert d.mode_name == "off"
    assert d.mode_desc == "off (bad does-not-exist)"
    assert d.mode_task is None
    assert d.services.storage.state["mode"] == "off"

    later = await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    assert later["ok"] is True and later["mode"] == "calm"
    await quiesce(d)


async def test_the_pattern_mode_gets_the_services_preset(monkeypatch):
    """Modes are built with the wired controller preset (its effect table)."""
    seen = []
    real_build = lifecycle.modes.build

    def spy(name, args, preset=None):
        seen.append(preset)
        return real_build(name, args, preset)

    monkeypatch.setattr(lifecycle.modes, "build", spy)
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "pattern", "args": {}})
    await quiesce(d)
    assert seen == [d.services.preset]


async def test_status_reports_the_mode_while_a_slow_connect_is_still_running():
    """Starting a mode powers the strip on first, which can block for tens of
    seconds on a slow BLE connect. `status` must report the mode being started,
    not "off" — otherwise the daemon looks idle while it is working."""
    d = make_daemon()
    gate = asyncio.Event()

    async def slow_power(on, reliable=False):
        await gate.wait()

    d.device.power = slow_power
    starting = asyncio.ensure_future(d.set_mode("solid", {"rgb": [1, 2, 3]}))
    await asyncio.sleep(0.05)
    try:
        status = await d.handle({"cmd": "status"})
        assert status["mode"] == "solid", f"reported {status['mode']!r} while starting solid"
    finally:
        gate.set()
        await starting
        await d._stop_mode()
