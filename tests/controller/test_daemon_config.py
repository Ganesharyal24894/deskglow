"""Daemon `config` command: validated settings, written through to Storage."""
import asyncio

import pytest
from daemon_support import make_daemon, quiesce

from deskglow.controller import lifecycle
from deskglow.controller.settings import SettingsStore


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


def saved_state(d):
    return SettingsStore(d.services.storage).load_state()


async def test_config_accepts_and_persists_known_keys():
    """`config` writes the setting through to the state file immediately."""
    d = make_daemon()
    for key, val in (("screen_monitor", "eDP-1-1"),
                     ("screen_style", "dominant"),
                     ("max_brightness", 40)):
        resp = await d.handle({"cmd": "config", "key": key, "value": val})
        assert resp == {"ok": True, key: val}
        assert saved_state(d)[key] == val


async def test_config_rejects_unknown_key():
    """An unknown config key is refused instead of silently stored."""
    d = make_daemon()
    resp = await d.handle({"cmd": "config", "key": "nope", "value": 1})
    assert resp["ok"] is False
    assert "nope" in resp["error"]
    assert "nope" not in saved_state(d)


@pytest.mark.parametrize("bad", ["abc", 500, -20])
async def test_config_validates_max_brightness(bad):
    """max_brightness must be a number in 0..100 — it divides every colour write."""
    d = make_daemon()
    resp = await d.handle({"cmd": "config", "key": "max_brightness", "value": bad})
    stored = saved_state(d)["max_brightness"]
    if resp.get("ok"):
        assert isinstance(stored, (int, float)) and not isinstance(stored, bool), \
            f"non-numeric {stored!r} persisted as max_brightness"
        assert 0 <= stored <= 100, f"out-of-range {stored!r} persisted"
    else:
        assert stored != bad, "rejected value must not be persisted"


async def test_bad_max_brightness_does_not_kill_the_running_mode():
    """Setting a bogus brightness must never take the running mode down with it."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [10, 20, 30]}})
    await d.handle({"cmd": "config", "key": "max_brightness", "value": "abc"})
    await asyncio.sleep(0.15)
    try:
        assert d.mode_name == "solid", f"mode collapsed to {d.mode_desc!r}"
        assert not d.mode_task.done()
    finally:
        await quiesce(d)
