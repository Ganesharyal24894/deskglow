"""drivers.win_autostart: the HKCU Run value, with a fake winreg (any OS)."""
import subprocess

import pytest

from deskglow.drivers import win_autostart
from deskglow.drivers.win_autostart import RUN_KEY, WindowsRunAutostart


class FakeKey:
    def __init__(self, reg, path):
        self.reg, self.path = reg, path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ, KEY_SET_VALUE, REG_SZ = 1, 2, 3

    def __init__(self):
        self.values = {}

    def OpenKey(self, root, path, reserved, access):
        assert (root, path) == ("HKCU", RUN_KEY)
        return FakeKey(self, path)

    CreateKeyEx = OpenKey

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        assert kind == self.REG_SZ
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def make(popen=None):
    reg = FakeWinreg()
    exe = r"C:\Program Files\Py\python.exe"
    auto = WindowsRunAutostart(winreg=reg, popen=popen, executable=exe)
    return auto, reg


def test_pythonw_is_used_when_it_sits_next_to_python():
    exe = r"C:\Py\python.exe"
    assert win_autostart.pythonw(exe, exists=lambda p: True).endswith("pythonw.exe")
    assert win_autostart.pythonw(exe, exists=lambda p: False) == exe


def test_enable_writes_a_quoted_run_value():
    auto, reg = make()          # no pythonw.exe at that made-up path: python.exe
    assert not auto.is_enabled()
    auto.set_enabled(True)
    assert reg.values["Deskglow"] == \
        '"C:\\Program Files\\Py\\python.exe" -m deskglow.app.daemon'
    assert auto.is_enabled()


def test_disable_removes_the_value_and_tolerates_absence():
    auto, reg = make()
    auto.set_enabled(True)
    auto.set_enabled(False)
    assert "Deskglow" not in reg.values
    auto.set_enabled(False)


def test_start_launches_the_daemon_detached_only_when_enabled():
    spawned = []
    auto, _ = make(popen=lambda argv, **kw: spawned.append((argv, kw)))
    assert auto.start() is False and spawned == []
    auto.set_enabled(True)
    assert auto.start() is True
    argv, kw = spawned[0]
    assert argv[1:] == ["-m", "deskglow.app.daemon"]
    assert kw["creationflags"] & 0x00000008, "not DETACHED_PROCESS"
    assert kw["stdout"] is subprocess.DEVNULL


def test_start_reports_a_launch_failure():
    def boom(argv, **kw):
        raise OSError("no such file")
    auto, _ = make(popen=boom)
    auto.set_enabled(True)
    assert auto.start() is False


@pytest.mark.parametrize("enabled", [True, False])
def test_is_enabled_reflects_the_registry(enabled):
    auto, reg = make()
    if enabled:
        reg.values["Deskglow"] = "x"
    assert auto.is_enabled() is enabled
