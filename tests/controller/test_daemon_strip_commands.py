"""Daemon strip management: scan, set_address, forget, monitors, favourites."""
import pytest
from daemon_support import make_daemon, quiesce
from fakes import FakeScanner, FakeStorage, make_services

from deskglow.controller import lifecycle
from deskglow.controller.daemon import Daemon
from deskglow.services.scanner import Advert

ELK = "0000fff0-0000-1000-8000-00805f9b34fb"


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


def daemon_with(scanner=None, screen=None, storage=None):
    kw = {"storage": storage or FakeStorage()}
    if scanner is not None:
        kw["scanner"] = scanner
    if screen is not None:
        kw["screen"] = screen
    d = make_daemon(storage=kw["storage"])
    d.services = make_services(**kw)
    return d


async def test_scan_returns_ranked_candidates_and_learns_the_strips_rssi():
    scanner = FakeScanner([
        Advert("11:11:11:11:11:11", "LEDBLE-1", -80, []),
        Advert("AA:BB:CC:DD:EE:FF", "ELK-BLEDOM", -58, [ELK]),
        Advert("22:22:22:22:22:22", "Headphones", -40, []),
    ])
    d = daemon_with(scanner)
    resp = await d.handle({"cmd": "scan", "timeout": 3})
    assert resp["ok"]
    assert [c["address"] for c in resp["candidates"]] == ["AA:BB:CC:DD:EE:FF", "11:11:11:11:11:11"]
    assert scanner.timeouts == [3.0]
    assert d.rssi == -58
    assert (await d.handle({"cmd": "status"}))["rssi"] == -58


@pytest.mark.parametrize("timeout,used", [(0, 1.0), (500, 30.0), (None, None)])
async def test_scan_timeout_is_clamped_or_rejected(timeout, used):
    scanner = FakeScanner([])
    d = daemon_with(scanner)
    resp = await d.handle({"cmd": "scan", "timeout": timeout})
    if used is None:
        assert resp["ok"] is False
    else:
        assert scanner.timeouts == [used]


async def test_scan_failure_is_reported_not_raised():
    d = daemon_with(FakeScanner(error=OSError("adapter off")))
    resp = await d.handle({"cmd": "scan"})
    assert resp == {"ok": False, "error": "scan failed: adapter off"}


async def test_set_address_saves_normalised_address_and_name_and_reconnects():
    storage = FakeStorage()
    d = daemon_with(storage=storage)
    resp = await d.handle({"cmd": "set_address", "address": "a4:c1:38:5e:22:9b",
                           "name": "MELK-OA10", "rssi": -61})
    assert resp["ok"] and resp["address"] == "A4:C1:38:5E:22:9B"
    assert storage.config == {"address": "A4:C1:38:5E:22:9B", "name": "MELK-OA10"}
    assert d.device.disconnects == 1 and d.device.backoff_resets == 1
    status = await d.handle({"cmd": "status"})
    assert status["device_name"] == "MELK-OA10" and status["rssi"] == -61
    await quiesce(d)


async def test_set_address_rejects_garbage_and_saves_nothing():
    storage = FakeStorage({"address": "AA:BB:CC:DD:EE:FF"})
    d = daemon_with(storage=storage)
    resp = await d.handle({"cmd": "set_address", "address": "not-a-mac"})
    assert resp["ok"] is False and "not a Bluetooth address" in resp["error"]
    assert storage.config_saves == 0


async def test_forget_stops_the_mode_and_clears_the_saved_strip():
    storage = FakeStorage({"address": "AA:BB:CC:DD:EE:FF", "name": "ELK"})
    d = daemon_with(storage=storage)
    await d.handle({"cmd": "set_mode", "mode": "calm", "args": {}})
    d.rssi = -50
    resp = await d.handle({"cmd": "forget"})
    assert resp["ok"]
    assert d.mode_name == "off" and d.mode_task is None
    assert storage.config == {}
    assert d.device.disconnects >= 1 and d.rssi is None
    assert d._idle_task is None


class _Screen:
    def __init__(self, monitors=None, error=None):
        self.m, self.error, self.closed = monitors, error, 0

    async def monitors(self):
        if self.error:
            raise self.error
        return self.m

    def close(self):
        self.closed += 1


async def test_monitors_lists_the_screens_and_closes_the_capture():
    scr = _Screen({"DP-1": {"left": 0, "top": 0, "width": 2560, "height": 1440}})
    d = daemon_with(screen=lambda: scr)
    resp = await d.handle({"cmd": "monitors"})
    assert resp == {"ok": True, "monitors": scr.m}
    assert scr.closed == 1


async def test_monitors_reports_unavailable_capture():
    d = Daemon(make_services(), log=lambda _m: None)   # default: screen unavailable
    resp = await d.handle({"cmd": "monitors"})
    assert resp["ok"] is False and "not available" in resp["error"]
    scr = _Screen(error=OSError("no display"))
    d2 = daemon_with(screen=lambda: scr)
    assert (await d2.handle({"cmd": "monitors"}))["ok"] is False and scr.closed == 1


async def test_favourite_add_and_remove_persist():
    storage = FakeStorage()
    d = daemon_with(storage=storage)
    resp = await d.handle({"cmd": "favourite_add", "color": "#123abc"})
    assert resp["favourites"][0] == "#123ABC" and len(resp["favourites"]) == 8
    assert storage.state["favourites"][0] == "#123ABC"
    resp = await d.handle({"cmd": "favourite_remove", "color": "#123ABC"})
    assert "#123ABC" not in resp["favourites"]
    assert (await d.handle({"cmd": "favourite_add", "color": "blue"}))["ok"] is False
