"""deskglow.controller.client.DaemonClient: ping, wait, ensure-running logic."""
import asyncio
import threading
import time

import pytest
from fakes import FakeAutostart, FakeIpcClient, FakeProcessControl

from deskglow.controller import client as client_mod
from deskglow.controller.client import DaemonClient


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(client_mod, "POLL_INTERVAL", 0.001)
    monkeypatch.setattr(client_mod, "START_WAIT", 0.05)


def make(reply=None, autostart=False):
    return DaemonClient(FakeIpcClient(reply), FakeAutostart(autostart), FakeProcessControl())


# --------------------------------------------------------------------- ping --

async def test_ping_sends_ping_and_reads_pong():
    c = make({"ok": True, "pong": True})
    assert await c.ping() is True
    assert c.ipc.requests == [{"cmd": "ping"}]


@pytest.mark.parametrize("reply", [None, {"ok": True}, FileNotFoundError("no socket"),
                                   asyncio.TimeoutError(), ValueError("garbage")])
async def test_ping_is_false_for_anything_but_a_pong(reply):
    assert await make(reply).ping() is False


# ------------------------------------------------------------ wait_for_daemon --

async def test_wait_returns_true_once_the_daemon_answers():
    answers = iter([None, None, {"pong": True}])
    c = make(lambda req: next(answers))
    assert await c.wait_for_daemon(timeout=5.0) is True
    assert len(c.ipc.requests) == 3


async def test_wait_gives_up_after_start_wait(monkeypatch):
    monkeypatch.setattr(client_mod, "START_WAIT", 0.05)
    c = make(None)
    t0 = time.monotonic()
    assert await c.wait_for_daemon() is False       # START_WAIT default
    assert time.monotonic() - t0 < 1.0, "did not honour START_WAIT"
    assert c.ipc.requests, "never polled"


# -------------------------------------------------------------- ensure_daemon --

async def test_a_running_daemon_is_used_as_is():
    c = make({"pong": True})
    assert await c.ensure_daemon() is True
    assert c.autostart.calls == 0
    assert c.process.spawns == 0


async def test_the_installed_service_is_preferred_over_spawning():
    up = {"v": False}

    class Starting(FakeAutostart):
        def start(self):
            self.calls += 1
            up["v"] = True
            return True

    c = DaemonClient(FakeIpcClient(lambda r: {"pong": True} if up["v"] else None),
                     Starting(), FakeProcessControl())
    assert await c.ensure_daemon() is True
    assert c.autostart.calls == 1
    assert c.process.spawns == 0


async def test_falls_back_to_spawning_when_no_service_is_installed():
    spawned = {"v": False}
    proc = FakeProcessControl()
    proc.spawn_daemon = lambda: spawned.__setitem__("v", True)
    c = DaemonClient(FakeIpcClient(lambda r: {"pong": True} if spawned["v"] else None),
                     FakeAutostart(False), proc)
    assert await c.ensure_daemon() is True
    assert spawned["v"]
    assert proc.try_begin_spawn(), "the spawn claim was not released"


async def test_an_autostart_that_raises_counts_as_not_installed():
    class Broken(FakeAutostart):
        def start(self):
            raise OSError("no systemctl")

    c = DaemonClient(FakeIpcClient(None), Broken(), FakeProcessControl())
    assert await c.ensure_daemon() is False
    assert c.process.spawns == 1


async def test_does_not_spawn_while_another_caller_holds_the_claim():
    c = make(None)
    assert c.process.try_begin_spawn()             # someone else is starting it
    assert await c.ensure_daemon() is False
    assert c.process.spawns == 0


async def test_claim_is_released_even_if_spawning_fails():
    c = make(None)

    def boom():
        raise OSError("fork failed")

    c.process.spawn_daemon = boom
    with pytest.raises(OSError):
        await c.ensure_daemon()
    assert c.process.try_begin_spawn(), "a failed spawn leaked the claim"


async def test_request_passes_the_timeout_through():
    seen = {}

    class Ipc(FakeIpcClient):
        async def request(self, message, timeout=25.0):
            seen["timeout"] = timeout
            return {"ok": True}

    c = DaemonClient(Ipc(), FakeAutostart(), FakeProcessControl())
    assert await c.request({"cmd": "status"}, timeout=3.0) == {"ok": True}
    assert seen["timeout"] == 3.0


def test_concurrent_ensure_daemon_spawns_at_most_one_daemon(monkeypatch):
    """Clients poll on fresh threads. With the daemon down, every poll used to
    race into spawning and fork another daemon."""
    proc = FakeProcessControl()
    monkeypatch.setattr(client_mod, "START_WAIT", 1.0)
    monkeypatch.setattr(client_mod, "POLL_INTERVAL", 0.01)
    # A barrier makes the overlap deterministic: every thread is inside
    # ensure_daemon() at the same moment, whatever the machine's load.
    n = 5
    start = threading.Barrier(n)

    def worker():
        start.wait(timeout=10)
        c = DaemonClient(FakeIpcClient(None), FakeAutostart(False), proc)
        asyncio.run(c.ensure_daemon())

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "a caller never finished"
    assert proc.spawns <= 1, f"spawned {proc.spawns} daemons concurrently"
