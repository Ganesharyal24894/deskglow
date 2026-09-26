"""x11_display.get_monitors: xrandr parsing with an mss fallback."""
import os
import sys

import pytest
from x11_support import DUAL, NEGATIVE_OFFSETS, SINGLE, fake_mss, fake_run

from deskglow.drivers import x11_display


@pytest.fixture
def clean_display_env():
    """Save/restore DISPLAY and XAUTHORITY: ensure_display_env writes to os.environ."""
    saved = {k: os.environ.get(k) for k in ("DISPLAY", "XAUTHORITY")}
    for k in saved:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def display_set(clean_display_env):
    """A session that already has DISPLAY/XAUTHORITY, so no systemctl lookup."""
    os.environ["DISPLAY"] = ":0"
    os.environ["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"


# -------------------------------------------------------- get_monitors ------

def test_get_monitors_parses_a_single_monitor(monkeypatch, display_set):
    """One monitor -> one entry keyed by its xrandr output name."""
    fake_run(monkeypatch, xrandr=SINGLE)
    assert x11_display.get_monitors() == {
        "eDP-1": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    }


def test_get_monitors_parses_a_dual_head_setup(monkeypatch, display_set):
    """Side-by-side monitors keep their own offsets."""
    fake_run(monkeypatch, xrandr=DUAL)
    assert x11_display.get_monitors() == {
        "HDMI-0": {"left": 0, "top": 0, "width": 1920, "height": 1080},
        "eDP-1-1": {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    }


def test_get_monitors_parses_negative_offsets(monkeypatch, display_set):
    """A monitor placed left of / above the primary has negative left/top."""
    assert x11_display.get_monitors is not None
    fake_run(monkeypatch, xrandr=NEGATIVE_OFFSETS)
    mons = x11_display.get_monitors()
    assert mons["eDP-1-1"] == {"left": -1920, "top": 120, "width": 1920, "height": 1080}
    assert mons["DP-2"] == {"left": 1920, "top": -200, "width": 2560, "height": 1440}


def test_get_monitors_ignores_the_header_line(monkeypatch, display_set):
    """The 'Monitors: N' header is not a monitor."""
    fake_run(monkeypatch, xrandr=DUAL)
    assert "Monitors:" not in x11_display.get_monitors()
    assert len(x11_display.get_monitors()) == 2


def test_get_monitors_uses_the_dimensions_not_the_millimetres(monkeypatch, display_set):
    """'1920/598' is pixels/millimetres; only the pixel count is geometry."""
    fake_run(monkeypatch, xrandr=SINGLE)
    rect = x11_display.get_monitors()["eDP-1"]
    assert (rect["width"], rect["height"]) == (1920, 1080)


def test_get_monitors_returns_empty_when_xrandr_missing_and_no_mss(monkeypatch, display_set):
    """xrandr not installed and mss unavailable -> {} instead of an exception."""
    fake_run(monkeypatch, raises=FileNotFoundError("xrandr"))
    monkeypatch.setitem(sys.modules, "mss", None)
    assert x11_display.get_monitors() == {}


def test_get_monitors_returns_empty_on_junk_output(monkeypatch, display_set):
    """Unparseable xrandr output plus no mss -> {}."""
    fake_run(monkeypatch, xrandr="totally unexpected\nnonsense here\n")
    monkeypatch.setitem(sys.modules, "mss", None)
    assert x11_display.get_monitors() == {}


def test_get_monitors_returns_empty_when_xrandr_prints_nothing(monkeypatch, display_set):
    """An X-less session (xrandr errors out, empty stdout) -> {}."""
    fake_run(monkeypatch, xrandr="")
    fake_mss(monkeypatch, raises=RuntimeError("no display"))
    assert x11_display.get_monitors() == {}


def test_get_monitors_falls_back_to_mss(monkeypatch, display_set):
    """When xrandr yields nothing usable, mss's monitor list is used instead."""
    fake_run(monkeypatch, xrandr="Monitors: 0\n")
    fake_mss(monkeypatch, monitors=[
        {"left": 0, "top": 0, "width": 3840, "height": 1080},     # [0] = all screens
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ])
    assert x11_display.get_monitors() == {
        "screen1": {"left": 0, "top": 0, "width": 1920, "height": 1080},
        "screen2": {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    }


def test_get_monitors_mss_fallback_skips_the_all_screens_entry(monkeypatch, display_set):
    """mss.monitors[0] is the virtual union rect and must not become 'screen1'."""
    fake_run(monkeypatch, xrandr="")
    fake_mss(monkeypatch, monitors=[
        {"left": 0, "top": 0, "width": 9999, "height": 9999},
        {"left": 0, "top": 0, "width": 1280, "height": 800},
    ])
    mons = x11_display.get_monitors()
    assert mons == {"screen1": {"left": 0, "top": 0, "width": 1280, "height": 800}}


def test_get_monitors_prefers_xrandr_over_mss(monkeypatch, display_set):
    """mss is only a fallback; real xrandr names win."""
    fake_run(monkeypatch, xrandr=SINGLE)
    fake_mss(monkeypatch, monitors=[{"left": 0, "top": 0, "width": 1, "height": 1},
                                    {"left": 0, "top": 0, "width": 1, "height": 1}])
    assert list(x11_display.get_monitors()) == ["eDP-1"]


def test_get_monitors_runs_xrandr_listmonitors(monkeypatch, display_set):
    """Pin the actual command line used to query geometry."""
    calls = []
    fake_run(monkeypatch, xrandr=SINGLE, calls=calls)
    x11_display.get_monitors()
    assert ["xrandr", "--listmonitors"] in calls
