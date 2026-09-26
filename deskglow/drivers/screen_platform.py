"""ScreenSource factories for macOS and Windows (mss, non-X11 monitor lists)."""
from . import win32_display
from .screen_mss import MssScreenSource


def mss_monitors(mss_factory=None):
    """{"screen1": rect, ...} from mss's own list (index 0 is the union); {}
    if no display is reachable."""
    try:
        if mss_factory is None:
            import mss
            mss_factory = mss.mss
        with mss_factory() as sct:
            return {f"screen{i}": {k: int(mon[k]) for k in ("left", "top", "width", "height")}
                    for i, mon in enumerate(sct.monitors[1:], start=1)}
    except Exception:
        return {}


def windows_monitors(list_win32=None, fallback=None):
    """Windows device names (DISPLAY1, ...) with their rects, else mss's list."""
    return (list_win32 or win32_display.list_monitors)() or (fallback or mss_monitors)()


def windows_screen(set_dpi_aware=None):
    """DPI awareness is process-wide and must precede the first grab, or mss
    captures a scaled-down, offset region on high-DPI displays."""
    (set_dpi_aware or win32_display.set_dpi_aware)()
    return MssScreenSource(list_monitors=windows_monitors)


def macos_screen():
    """Needs the Screen Recording permission (without it macOS hands back
    only the wallpaper, silently)."""
    return MssScreenSource(list_monitors=mss_monitors)
