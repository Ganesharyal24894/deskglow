"""Win32 display/focus via ctypes, Quartz focus, and the mss-based monitor
lists — all with fakes, so they run on any OS."""
import ctypes
import types

from deskglow.drivers import screen_platform, win32_display
from deskglow.drivers.focus_other import (NoFocusTracker, QuartzFocusTracker,
                                          Win32FocusTracker)

MONITORS = {101: ("\\\\.\\DISPLAY1", (0, 0, 2560, 1440)),
            102: ("\\\\.\\DISPLAY2", (-1920, 200, 0, 1280))}


class FakeUser32:
    def __init__(self, foreground=0, hmon=102, cursor=(5, 6)):
        self.foreground, self.hmon, self.cursor = foreground, hmon, cursor
        self.calls = []

    def EnumDisplayMonitors(self, hdc, clip, callback, lparam):
        for h in MONITORS:
            callback(h, None, None, 0)
        return 1

    def GetMonitorInfoW(self, hmon, ref):
        info = ref._obj
        assert info.cbSize == ctypes.sizeof(win32_display.MONITORINFOEXW)
        if hmon not in MONITORS:
            return 0
        name, (left, top, r, b) = MONITORS[hmon]
        info.szDevice = name
        info.rcMonitor.left, info.rcMonitor.top = left, top
        info.rcMonitor.right, info.rcMonitor.bottom = r, b
        return 1

    def GetForegroundWindow(self):
        return self.foreground

    def MonitorFromWindow(self, hwnd, flags):
        self.calls.append(("MonitorFromWindow", hwnd, flags))
        return self.hmon

    def GetCursorPos(self, ref):
        ref._obj.x, ref._obj.y = self.cursor
        return 1


def test_list_monitors_uses_windows_device_names_and_rects():
    mons = win32_display.list_monitors(FakeUser32(), ctypes.CFUNCTYPE)
    assert mons == {"DISPLAY1": {"left": 0, "top": 0, "width": 2560, "height": 1440},
                    "DISPLAY2": {"left": -1920, "top": 200, "width": 1920, "height": 1080}}


def test_list_monitors_is_empty_rather_than_raising():
    assert win32_display.list_monitors(object(), ctypes.CFUNCTYPE) == {}


def test_focus_is_the_centre_of_the_foreground_windows_monitor():
    u = FakeUser32(foreground=0x5555, hmon=102)
    assert Win32FocusTracker(u).center() == (-960, 740)
    assert u.calls == [("MonitorFromWindow", 0x5555, 2)], "must use DEFAULTTONEAREST"


def test_focus_falls_back_to_the_cursor_without_a_foreground_window():
    assert Win32FocusTracker(FakeUser32(foreground=0)).center() == (5, 6)


def test_focus_is_none_when_win32_is_unusable():
    t = Win32FocusTracker(object())
    assert t.center() is None
    t.close()


def test_dpi_awareness_prefers_per_monitor_and_falls_back():
    calls = []
    shcore = types.SimpleNamespace(SetProcessDpiAwareness=lambda v: calls.append(("shcore", v)))
    assert win32_display.set_dpi_aware(types.SimpleNamespace(shcore=shcore)) is True
    assert calls == [("shcore", 2)]

    def refuse(v):
        raise OSError("win8.0")
    old = types.SimpleNamespace(shcore=types.SimpleNamespace(SetProcessDpiAwareness=refuse),
                                user32=types.SimpleNamespace(SetProcessDPIAware=lambda: 1))
    assert win32_display.set_dpi_aware(old) is True
    assert win32_display.set_dpi_aware(types.SimpleNamespace()) is False


def test_windows_screen_is_dpi_aware_before_any_grab():
    order = []
    src = screen_platform.windows_screen(set_dpi_aware=lambda: order.append("dpi"))
    assert order == ["dpi"]
    assert src._list_monitors is screen_platform.windows_monitors
    src.close()


class FakeSct:
    monitors = [{"left": 0, "top": 0, "width": 3000, "height": 1000},
                {"left": 0, "top": 0, "width": 1000, "height": 1000},
                {"left": 1000, "top": 0, "width": 2000, "height": 1000}]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_mss_monitors_are_named_screen1_onwards_skipping_the_union():
    assert screen_platform.mss_monitors(FakeSct) == {
        "screen1": {"left": 0, "top": 0, "width": 1000, "height": 1000},
        "screen2": {"left": 1000, "top": 0, "width": 2000, "height": 1000}}

    def broken():
        raise RuntimeError("no display")
    assert screen_platform.mss_monitors(broken) == {}


def test_windows_monitors_fall_back_to_mss_names():
    assert screen_platform.windows_monitors(lambda: {}, lambda: {"screen1": 1}) == {"screen1": 1}
    assert screen_platform.windows_monitors(lambda: {"DISPLAY1": 2}, lambda: 1 / 0) == {
        "DISPLAY1": 2}


def quartz(windows):
    return types.SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1, kCGWindowListExcludeDesktopElements=16,
        kCGNullWindowID=0, CGWindowListCopyWindowInfo=lambda opts, wid: (
            windows if (opts, wid) == (17, 0) else []))


def test_quartz_focus_is_the_first_layer_0_window():
    wins = [{"kCGWindowLayer": 25, "kCGWindowBounds": {"X": 0, "Y": 0, "Width": 50, "Height": 20}},
            {"kCGWindowLayer": 0, "kCGWindowBounds": {"X": 1440, "Y": 100, "Width": 800,
                                                      "Height": 600}},
            {"kCGWindowLayer": 0, "kCGWindowBounds": {"X": 0, "Y": 0, "Width": 10, "Height": 10}}]
    assert QuartzFocusTracker(quartz(wins)).center() == (1840, 400)


def test_quartz_focus_is_none_without_windows_or_quartz():
    assert QuartzFocusTracker(quartz([])).center() is None
    assert QuartzFocusTracker(object()).center() is None


def test_wayland_has_no_focus_tracking():
    t = NoFocusTracker()
    assert t.center() is None
    t.close()
