"""FocusTrackers for Windows (Win32), macOS (Quartz) and Wayland (none).

Each degrades to None rather than raising; screen mode then falls back to the
first (Wayland: the portal-selected) monitor.
"""
from . import win32_display


class Win32FocusTracker:
    """GetForegroundWindow -> MonitorFromWindow -> that monitor's centre."""

    def __init__(self, user32=None):
        self._user32 = user32

    def center(self):
        return win32_display.foreground_monitor_center(self._user32)

    def close(self):
        pass


def _quartz():
    import Quartz
    return Quartz


class QuartzFocusTracker:
    """The frontmost normal window (layer 0) in CGWindowList's front-to-back
    order. Reading window bounds needs no permission; titles would."""

    def __init__(self, quartz=None):
        self._q = quartz

    def center(self):
        try:
            q = self._q or _quartz()
            opts = q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements
            for win in q.CGWindowListCopyWindowInfo(opts, q.kCGNullWindowID) or []:
                if win.get("kCGWindowLayer", 0) != 0:
                    continue
                b = win.get("kCGWindowBounds") or {}
                x, y = float(b.get("X", 0)), float(b.get("Y", 0))
                w, h = float(b.get("Width", 0)), float(b.get("Height", 0))
                if w > 0 and h > 0:
                    return (int(x + w / 2), int(y + h / 2))
        except Exception:
            pass
        return None

    def close(self):
        pass


class NoFocusTracker:
    """Wayland: no protocol exposes the focused window's position to us."""

    def center(self):
        return None

    def close(self):
        pass
