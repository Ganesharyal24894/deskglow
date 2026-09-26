"""Daemon background work: the connectivity watchdog, the reaper, task lifetime."""
import asyncio

import pytest
from daemon_support import make_daemon
from fakes import ExitCalled

from deskglow.controller import lifecycle
from deskglow.controller.lifecycle import ModeLifecycle


def _patch_sleep(monkeypatch, stop_after=None, stop_event=None):
    """Make asyncio.sleep instant, optionally stopping the loop after N calls."""
    real_sleep = asyncio.sleep
    calls = {"n": 0, "delays": []}

    async def fake_sleep(delay, *a, **kw):
        calls["n"] += 1
        calls["delays"].append(delay)
        if stop_after is not None and calls["n"] >= stop_after:
            stop_event.set()
        return await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return calls


async def test_watchdog_exits_after_the_documented_failure_threshold(monkeypatch):
    """40 consecutive connect failures means the process recycles itself."""
    d = make_daemon()
    d.device.consecutive_failures = 40
    calls = _patch_sleep(monkeypatch)
    with pytest.raises(ExitCalled):
        await asyncio.wait_for(ModeLifecycle._watchdog(d), timeout=5.0)
    assert d.services.process.exits == [1]
    assert calls["delays"][0] == lifecycle.WATCHDOG_PERIOD == 60


async def test_watchdog_tolerates_failures_below_the_threshold(monkeypatch):
    """One flaky patch is not a reason to restart: 39 failures must be survived."""
    d = make_daemon()
    d.device.consecutive_failures = 39
    _patch_sleep(monkeypatch, stop_after=5, stop_event=d._stop)
    await asyncio.wait_for(ModeLifecycle._watchdog(d), timeout=5.0)  # no exit
    assert d.services.process.exits == []


async def test_watchdog_never_exits_while_no_strip_is_configured(monkeypatch):
    """Before `deskglow setup` there is nothing to connect to — don't restart-loop."""
    d = make_daemon()
    d.device.address = None
    d.device.consecutive_failures = 1000
    _patch_sleep(monkeypatch, stop_after=5, stop_event=d._stop)
    await asyncio.wait_for(ModeLifecycle._watchdog(d), timeout=5.0)  # no exit
    assert d.services.process.exits == []


async def _stubborn(release):
    """A task that swallows every cancel() (like a mode stuck in a slow BLE op)
    until `release` is set."""
    while not release.is_set():
        try:
            await release.wait()
        except asyncio.CancelledError:
            continue


async def test_reaper_exits_for_a_restart_when_a_mode_will_not_die(monkeypatch):
    """A mode task that ignores every cancel() ends in a clean process restart."""
    d = make_daemon()
    release = asyncio.Event()
    task = asyncio.ensure_future(_stubborn(release))
    await asyncio.sleep(0)
    d._orphans.add(task)
    _patch_sleep(monkeypatch)
    try:
        with pytest.raises(ExitCalled):
            await d._reap(task)
        assert d.services.process.exits == [1]
        assert task not in d._orphans
        assert not task.done(), "the stubborn task was expected to survive every cancel"
    finally:
        release.set()
        await task


async def test_reaper_returns_quietly_once_the_task_finishes(monkeypatch):
    """A task that does stop after a later cancel() needs no restart."""
    d = make_daemon()
    task = asyncio.ensure_future(asyncio.Event().wait())
    d._orphans.add(task)
    _patch_sleep(monkeypatch)
    await d._reap(task)
    assert task.done()
    assert d.services.process.exits == []
    assert task not in d._orphans


async def test_background_tasks_are_strongly_referenced():
    """asyncio only keeps weak references to running tasks: a fire-and-forget
    create_task() can be garbage collected mid-flight. The daemon must hold on
    to its watchdog and reaper tasks."""
    d = make_daemon()
    del d._watchdog                     # use the real watchdog
    d.start_background_tasks()
    try:
        refs = getattr(d, "_bg_tasks", None)
        assert refs, "daemon keeps no strong reference to its background tasks"
        assert any(not t.done() for t in refs)
    finally:
        await d.shutdown_background_tasks()
    assert d._bg_tasks == set()


async def test_idle_disconnect_task_is_cancelled_on_shutdown():
    """Switching off schedules a delayed disconnect; shutting down must cancel it
    rather than leaving a pending task to be destroyed by the loop."""
    d = make_daemon()
    await d.set_mode("off", {})
    assert d._idle_task is not None and not d._idle_task.done()
    await d.shutdown_background_tasks()
    assert d._idle_task is None or d._idle_task.cancelled() or d._idle_task.done()
