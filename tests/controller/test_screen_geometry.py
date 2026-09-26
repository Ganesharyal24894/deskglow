"""Monitor geometry for screen mode: which rect contains a point, and the
rect covering every monitor. Pure functions, no display."""
import pytest

from deskglow.controller.modes.geometry import bounding_rect, pick_monitor


# --------------------------------------------------------- pick_monitor -----

MONITORS = {
    "HDMI-0": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    "eDP-1-1": {"left": 1920, "top": 0, "width": 1280, "height": 800},
    "DP-2": {"left": -1600, "top": -200, "width": 1600, "height": 900},
}


@pytest.mark.parametrize("point,expected", [
    ((0, 0), "HDMI-0"),
    ((960, 540), "HDMI-0"),
    ((1919, 1079), "HDMI-0"),          # last pixel still belongs to HDMI-0
    ((1920, 0), "eDP-1-1"),            # first pixel of the next monitor
    ((2500, 400), "eDP-1-1"),
    ((-1600, -200), "DP-2"),           # top-left corner is inclusive
    ((-800, 300), "DP-2"),
])
def test_pick_monitor_finds_the_monitor_containing_the_point(point, expected):
    """A point maps to the monitor whose half-open rect contains it."""
    assert pick_monitor(MONITORS, point) == MONITORS[expected]


@pytest.mark.parametrize("point", [
    (5000, 5000),          # right of everything
    (-9999, -9999),        # left of everything
    (0, 5000),             # below
    (3200, 0),             # in the gap past eDP-1-1's right edge
])
def test_pick_monitor_falls_back_to_the_first_monitor(point):
    """A point on no monitor falls back to the first known monitor."""
    assert pick_monitor(MONITORS, point) == MONITORS["HDMI-0"]


def test_pick_monitor_with_no_point_uses_the_first_monitor():
    """point=None (no focused window, no pointer) -> first monitor."""
    assert pick_monitor(MONITORS, None) == MONITORS["HDMI-0"]


def test_pick_monitor_returns_the_only_monitor():
    """Single-head: every point resolves to that monitor."""
    one = {"eDP-1": {"left": 0, "top": 0, "width": 1920, "height": 1080}}
    assert pick_monitor(one, (10**6, 10**6)) == one["eDP-1"]
    assert pick_monitor(one, None) == one["eDP-1"]


def test_pick_monitor_returns_the_live_rect_object():
    """The returned rect is one of the monitors dict's own rects."""
    got = pick_monitor(MONITORS, (100, 100))
    assert any(got is r for r in MONITORS.values())


# -------------------------------------------------------- bounding_rect -----

def test_bounding_rect_single_monitor():
    """One monitor: the bounding rect is that monitor."""
    one = {"eDP-1": {"left": 0, "top": 0, "width": 1920, "height": 1080}}
    assert bounding_rect(one) == {"left": 0, "top": 0,
                                              "width": 1920, "height": 1080}


def test_bounding_rect_side_by_side():
    """Two side-by-side monitors give one wide rect."""
    mons = {
        "a": {"left": 0, "top": 0, "width": 1920, "height": 1080},
        "b": {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    }
    assert bounding_rect(mons) == {"left": 0, "top": 0,
                                               "width": 3840, "height": 1080}


def test_bounding_rect_covers_negative_offsets():
    """Monitors left of / above the origin extend the rect, not clip it."""
    assert bounding_rect(MONITORS) == {
        "left": -1600,          # DP-2's left edge
        "top": -200,            # DP-2's top edge
        "width": 3200 + 1600,   # -1600 .. 3200
        "height": 1080 + 200,   # -200 .. 1080
    }


def test_bounding_rect_contains_every_monitor():
    """Every monitor rect is fully inside the bounding rect."""
    b = bounding_rect(MONITORS)
    for r in MONITORS.values():
        assert b["left"] <= r["left"]
        assert b["top"] <= r["top"]
        assert b["left"] + b["width"] >= r["left"] + r["width"]
        assert b["top"] + b["height"] >= r["top"] + r["height"]


def test_bounding_rect_of_stacked_monitors():
    """Vertically stacked monitors give one tall rect."""
    mons = {
        "a": {"left": 0, "top": 0, "width": 1920, "height": 1080},
        "b": {"left": 0, "top": -1080, "width": 1920, "height": 1080},
    }
    assert bounding_rect(mons) == {"left": 0, "top": -1080,
                                               "width": 1920, "height": 2160}
