"""XlibFocusTracker: the focused window's centre, pointer fallback, cleanup.

No X server is touched: `Xlib` is stubbed in sys.modules and the display
comes from an injected factory.
"""
import sys
import types

import pytest

from deskglow.drivers import focus_x11, x11_display


class Geo:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeWindow:
    def get_geometry(self):
        return Geo(width=200, height=100)

    def translate_coords(self, _root, _x, _y):
        return Geo(x=1000, y=40)


class FakeRoot:
    def __init__(self, active=(42,), pointer=(7, 9), prop_error=None):
        self.active = active
        self.pointer = pointer
        self.prop_error = prop_error

    def get_full_property(self, atom, kind):
        if self.prop_error is not None:
            raise self.prop_error
        return Geo(value=list(self.active)) if self.active is not None else None

    def query_pointer(self):
        if self.pointer is None:
            raise RuntimeError("no pointer")
        return Geo(root_x=self.pointer[0], root_y=self.pointer[1])


class FakeDisplay:
    def __init__(self, root):
        self.root = root
        self.closed = 0

    def screen(self):
        return Geo(root=self.root)

    def intern_atom(self, name):
        return name

    def create_resource_object(self, kind, wid):
        assert (kind, wid) == ("window", 42)
        return FakeWindow()

    def close(self):
        self.closed += 1


@pytest.fixture(autouse=True)
def fake_xlib(monkeypatch):
    xlib = types.ModuleType("Xlib")
    xlib.X = types.SimpleNamespace(AnyPropertyType=0)
    xlib.display = types.ModuleType("Xlib.display")
    monkeypatch.setitem(sys.modules, "Xlib", xlib)
    monkeypatch.setitem(sys.modules, "Xlib.display", xlib.display)
    monkeypatch.setattr(x11_display, "ensure_display_env", lambda: None)


def tracker(**root_kw):
    disp = FakeDisplay(FakeRoot(**root_kw))
    return focus_x11.XlibFocusTracker(display_factory=lambda: disp), disp


def test_center_is_the_middle_of_the_focused_window():
    t, _d = tracker()
    assert t.center() == (1100, 90)


@pytest.mark.parametrize("root_kw", [
    {"active": None},                       # no _NET_ACTIVE_WINDOW property
    {"active": (0,)},                       # property present but no window
    {"prop_error": RuntimeError("BadWindow")},
])
def test_falls_back_to_the_pointer(root_kw):
    t, _d = tracker(**root_kw)
    assert t.center() == (7, 9)


def test_none_when_neither_window_nor_pointer_is_known():
    t, _d = tracker(active=None, pointer=None)
    assert t.center() is None


def test_none_when_the_display_cannot_be_opened():
    def boom():
        raise RuntimeError("Can't connect to display")
    t = focus_x11.XlibFocusTracker(display_factory=boom)
    assert t.center() is None
    t.close()            # nothing to close, must not raise


def test_close_releases_the_display_once():
    t, d = tracker()
    t.close()
    t.close()
    assert d.closed == 1
    assert t.center() is None, "a closed tracker must not touch the display"


def test_close_survives_a_display_that_raises():
    t, d = tracker()

    def boom():
        raise OSError("connection gone")

    d.close = boom
    t.close()            # must not raise
