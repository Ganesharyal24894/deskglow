"""Daemon persistence: mode, args and settings survive a restart via Storage."""
import pytest
from daemon_support import make_daemon, quiesce
from fakes import FakeStorage, make_services

from deskglow.controller import lifecycle
from deskglow.controller.daemon import Daemon


@pytest.fixture(autouse=True)
def fast_idle(monkeypatch):
    monkeypatch.setattr(lifecycle, "IDLE_DISCONNECT", 0.02)


async def test_state_file_records_mode_and_args():
    """A restart must be able to bring back the exact mode, arguments included."""
    d = make_daemon()
    args = {"name": "blink-cyan", "speed": 77}
    await d.handle({"cmd": "set_mode", "mode": "pattern", "args": args})
    await quiesce(d)

    saved = d.services.storage.state
    assert saved["mode"] == "pattern"
    assert saved["args"] == args


async def test_off_clears_the_persisted_args():
    """Off must not leave the previous mode's args behind for the next start."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "solid", "args": {"rgb": [4, 5, 6]}})
    await d.handle({"cmd": "off"})
    await quiesce(d)
    state = d.services.storage.state
    assert state["mode"] == "off"
    assert state["args"] == {}


async def test_screen_style_arg_is_persisted_as_a_setting():
    """`screen vivid` remembers the style so a bare `screen` keeps using it."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "screen", "args": {"style": "edge"}})
    await quiesce(d)
    assert d.services.storage.state["screen_style"] == "edge"


async def test_a_bad_screen_style_arg_is_ignored_not_persisted():
    """An unknown style is logged and dropped; the stored style is untouched."""
    d = make_daemon()
    await d.handle({"cmd": "set_mode", "mode": "screen", "args": {"style": "neon"}})
    await quiesce(d)
    assert d.services.storage.state["screen_style"] == "vivid"
    assert d.mode_name == "screen"


async def test_daemon_boots_from_the_saved_state_topped_up_with_defaults():
    """A partial saved state is completed with every default key."""
    d = make_daemon(storage=FakeStorage(state={"mode": "calm", "max_brightness": 30}))
    assert d.state["mode"] == "calm"
    assert d.state["max_brightness"] == 30
    assert d.state["screen_style"] == "vivid"
    assert d.state["args"] == {}


async def test_the_device_reads_the_configured_address_from_storage():
    """The strip address comes from Storage (env override first, then config)."""
    storage = FakeStorage(config={"address": "AA:00:00:00:00:01"},
                          override="BB:00:00:00:00:02")
    d = Daemon(make_services(storage=storage))
    assert d.device.address == "BB:00:00:00:00:02"
    storage.override = None
    assert d.device.address == "AA:00:00:00:00:01"
