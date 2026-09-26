"""drivers.bluez: bond removal and adapter reset via bluetoothctl (never run for real)."""
import subprocess

import pytest

from deskglow.drivers import bluez
from deskglow.services.link import AdapterError

ADDR = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def dbus_down(monkeypatch):
    """D-Bus RemoveDevice fails, so drop_bond falls back to bluetoothctl."""
    def refuse(address):
        raise bluez.bluez_dbus.DbusError("no system bus in tests")
    monkeypatch.setattr(bluez.bluez_dbus, "remove_device", refuse)


@pytest.fixture
def runs(monkeypatch, dbus_down):
    box = {"calls": [], "raise": None}

    def fake_run(cmd, *a, **kw):
        box["calls"].append(list(cmd))
        if box["raise"] is not None:
            raise box["raise"]
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(bluez.subprocess, "run", fake_run)
    return box


def test_drop_bond_falls_back_to_bluetoothctl_when_dbus_fails(runs):
    bluez.drop_bond(ADDR)
    assert runs["calls"] == [["bluetoothctl", "remove", ADDR]]


def test_drop_bond_prefers_dbus_and_then_skips_bluetoothctl(runs):
    removed = []
    bluez.drop_bond(ADDR, dbus_remove=removed.append)
    assert removed == [ADDR]
    assert runs["calls"] == [], "bluetoothctl ran although D-Bus succeeded"


@pytest.mark.parametrize("exc", [FileNotFoundError("bluetoothctl"),
                                 subprocess.TimeoutExpired("bluetoothctl", 10)])
def test_drop_bond_never_raises(runs, exc):
    runs["raise"] = exc
    bluez.drop_bond(ADDR)          # must not raise


def test_reset_adapter_power_cycles_then_drops_the_bond(runs):
    """`repair` bounces the adapter, then forgets the stale bond."""
    sleeps = []
    bluez.reset_adapter(ADDR, sleep=sleeps.append)
    assert runs["calls"] == [
        ["bluetoothctl", "power", "off"],
        ["bluetoothctl", "power", "on"],
        ["bluetoothctl", "remove", ADDR],
    ]
    assert sleeps == [bluez.RESET_PAUSE, bluez.RESET_PAUSE]


def test_reset_adapter_without_an_address_skips_the_bond_removal(runs):
    bluez.reset_adapter(None, sleep=lambda _s: None)
    assert runs["calls"] == [["bluetoothctl", "power", "off"],
                             ["bluetoothctl", "power", "on"]]


def test_missing_bluetoothctl_is_a_clear_adapter_error(runs):
    """A box without BlueZ tools gets advice, not a traceback."""
    runs["raise"] = FileNotFoundError(2, "No such file or directory: 'bluetoothctl'")
    with pytest.raises(AdapterError) as exc:
        bluez.reset_adapter(ADDR, sleep=lambda _s: None)
    assert "bluetoothctl" in str(exc.value)
    assert "BlueZ" in str(exc.value)


def test_a_failing_bluetoothctl_is_an_adapter_error(runs):
    runs["raise"] = subprocess.TimeoutExpired("bluetoothctl", 12)
    with pytest.raises(AdapterError, match="bluetoothctl failed"):
        bluez.reset_adapter(ADDR, sleep=lambda _s: None)
