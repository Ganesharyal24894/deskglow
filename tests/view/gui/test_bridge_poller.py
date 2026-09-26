"""ThreadBridge (worker thread, replies on the Qt thread) and StatusPoller
(2 s polling without overlapping requests)."""
import asyncio
import threading

import pytest
from gui_fakes import FakeClient, HeldBridge, SyncBridge

from deskglow.view.gui import poller as poller_mod
from deskglow.view.gui.bridge import ThreadBridge
from deskglow.view.gui.poller import StatusPoller


@pytest.fixture
def bridge(qapp):
    made = []

    def make(client):
        b = ThreadBridge(client)
        made.append(b)
        return b
    yield make
    for b in made:
        b.stop()


def wait_reply(qtbot, bridge, req):
    got = {}

    def cb(reply):
        got["reply"], got["thread"] = reply, threading.current_thread()
    bridge.request(req, cb)
    qtbot.waitUntil(lambda: "reply" in got, timeout=3000)
    return got


def test_request_runs_off_the_qt_thread_and_replies_on_it(qtbot, bridge):
    seen = {}

    class Client(FakeClient):
        async def request(self, req, timeout=25.0):
            seen["thread"] = threading.current_thread()
            return await super().request(req, timeout)

    got = wait_reply(qtbot, bridge(Client()), {"cmd": "status"})
    assert got["reply"]["ok"] is True
    assert seen["thread"] is not threading.main_thread()
    assert got["thread"] is threading.main_thread()


def test_daemon_that_cannot_be_started_is_a_failure_reply(qtbot, bridge):
    c = FakeClient()
    c.daemon_up = False
    got = wait_reply(qtbot, bridge(c), {"cmd": "status"})
    assert got["reply"] == {"ok": False, "error": "the Deskglow service is not running"}
    assert c.requests == []


def test_ensure_daemon_once_then_again_after_a_failure(qtbot, bridge):
    c = FakeClient()
    b = bridge(c)
    wait_reply(qtbot, b, {"cmd": "status"})
    wait_reply(qtbot, b, {"cmd": "status"})
    assert c.ensures == 1
    c.replies["boom"] = OSError("socket gone")
    got = wait_reply(qtbot, b, {"cmd": "boom"})
    assert got["reply"]["ok"] is False and "socket gone" in got["reply"]["error"]
    wait_reply(qtbot, b, {"cmd": "status"})
    assert c.ensures == 2


def test_a_non_dict_reply_is_a_failure(qtbot, bridge):
    c = FakeClient()
    c.replies["x"] = lambda req: None
    assert wait_reply(qtbot, bridge(c), {"cmd": "x"})["reply"]["ok"] is False


def test_call_runs_blocking_work_and_returns_exceptions(qtbot, bridge):
    b = bridge(FakeClient())
    out = []
    b.call(lambda: 41 + 1, out.append)
    b.call(lambda: 1 / 0, out.append)

    def refuse():
        raise OSError("systemctl refused")
    b.call(refuse, out.append)
    qtbot.waitUntil(lambda: len(out) == 3, timeout=3000)
    assert out[0] == 42 and isinstance(out[1], ZeroDivisionError)
    assert isinstance(out[2], OSError)


def test_a_failing_callback_does_not_break_the_bridge(qtbot, bridge):
    b = bridge(FakeClient())

    def bad(_reply):
        raise RuntimeError("bug in a screen")
    b.request({"cmd": "status"}, bad)
    assert wait_reply(qtbot, b, {"cmd": "status"})["reply"]["ok"]


def test_the_ui_thread_is_never_blocked_by_a_slow_daemon(qtbot, bridge):
    class Slow(FakeClient):
        async def request(self, req, timeout=25.0):
            await asyncio.sleep(0.3)
            return {"ok": True}
    b = bridge(Slow())
    got = []
    b.request({"cmd": "status"}, got.append)
    assert got == []          # returned at once; the reply comes later
    qtbot.waitUntil(lambda: bool(got), timeout=3000)


def test_poller_never_overlaps_requests(qapp):
    held = HeldBridge(FakeClient())
    p = StatusPoller(held)
    replies = []
    p.updated.connect(replies.append)
    p.poll()
    p.poll()                  # a timer tick while one is in flight: skipped
    assert len(held.held) == 1 and p.in_flight
    held.release()
    assert replies and replies[0]["ok"] and not p.in_flight


def test_refresh_while_in_flight_polls_again_right_after(qapp):
    held = HeldBridge(FakeClient())
    p = StatusPoller(held)
    p.poll()
    p.refresh()
    p.refresh()
    assert len(held.held) == 1
    held.release()
    assert len(held.held) == 1      # exactly one follow-up
    held.release()
    assert held.held == []


def test_poll_interval_is_two_seconds_and_fast_mode_is_quicker(qapp):
    p = StatusPoller(HeldBridge(FakeClient()))
    assert p.interval() == 2000 == poller_mod.INTERVAL_MS
    p.set_fast(True)
    assert p.interval() == poller_mod.FAST_MS < 2000
    p.set_fast(False)
    assert p.interval() == 2000


def test_timer_drives_polls(qtbot):
    client = FakeClient()
    p = StatusPoller(SyncBridge(client), interval_ms=20)
    p.start()
    qtbot.waitUntil(lambda: len(client.requests) >= 3, timeout=2000)
    p.stop()
    assert all(r == {"cmd": "status"} for r in client.requests)


def test_stop_cancels_in_flight_work_and_ignores_later_requests(qtbot, bridge):
    started = threading.Event()

    class Hang(FakeClient):
        async def request(self, req, timeout=25.0):
            started.set()
            await asyncio.sleep(60)

    b = bridge(Hang())
    got = []
    b.request({"cmd": "status"}, got.append)
    assert started.wait(2.0)
    b.stop()
    assert not b._thread.is_alive() and b._loop.is_closed()
    assert b.request({"cmd": "status"}, got.append) is None
    b.stop()                                   # idempotent
