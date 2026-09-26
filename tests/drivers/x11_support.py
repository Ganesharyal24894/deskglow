"""Fakes for the X11 display driver tests: no X server, no xrandr, no mss."""
import subprocess
import sys
import types


# ------------------------------------------------------------- helpers ------

class FakeCompleted:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def fake_run(monkeypatch, *, xrandr="", systemctl="", raises=None, calls=None):
    """Install a subprocess.run that never spawns anything."""

    def _run(cmd, *args, **kwargs):
        if calls is not None:
            calls.append(list(cmd))
        if raises is not None:
            raise raises
        prog = cmd[0] if isinstance(cmd, (list, tuple)) else str(cmd)
        if prog == "xrandr":
            return FakeCompleted(xrandr)
        if prog == "systemctl":
            return FakeCompleted(systemctl)
        raise AssertionError(f"unexpected subprocess call: {cmd!r}")

    monkeypatch.setattr(subprocess, "run", _run)
    return _run


def fake_mss(monkeypatch, monitors=None, raises=None):
    """Install a stub `mss` module in sys.modules for the lazy imports."""

    class _Sct:
        def __init__(self):
            self.monitors = monitors or []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _factory():
        if raises is not None:
            raise raises
        return _Sct()

    mod = types.ModuleType("mss")
    mod.mss = _factory
    monkeypatch.setitem(sys.modules, "mss", mod)
    return mod


# ------------------------------------------------------- xrandr fixtures ----

SINGLE = """Monitors: 1
 0: +*eDP-1 1920/344x1080/193+0+0  eDP-1
"""

DUAL = """Monitors: 2
 0: +*HDMI-0 1920/598x1080/336+0+0  HDMI-0
 1: +eDP-1-1 1920/344x1080/193+1920+0  eDP-1-1
"""

NEGATIVE_OFFSETS = """Monitors: 3
 0: +*HDMI-0 1920/598x1080/336+0+0  HDMI-0
 1: +eDP-1-1 1920/344x1080/193+-1920+120  eDP-1-1
 2: +DP-2 2560/597x1440/336+1920+-200  DP-2
"""
