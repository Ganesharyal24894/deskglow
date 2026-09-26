"""Win32 display helpers via ctypes: DPI awareness, monitor names and rects,
and the monitor under the foreground window.

Nothing Windows-only is touched at import time: `windll` / `WINFUNCTYPE` are
looked up when called (and injectable, so tests run on any OS).
"""
import ctypes

MONITOR_DEFAULTTONEAREST = 2
PROCESS_PER_MONITOR_DPI_AWARE = 2


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong), ("szDevice", ctypes.c_wchar * 32)]


def _windll(windll):
    return windll if windll is not None else ctypes.windll


def set_dpi_aware(windll=None):
    """Make the process per-monitor DPI aware so mss grabs (and Win32 rects)
    are in real pixels. Must run before the first grab. Never raises."""
    try:
        w = _windll(windll)
    except Exception:
        return False
    try:
        w.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        return True
    except Exception:
        pass
    try:                                   # Windows 8.0 and older
        return bool(w.user32.SetProcessDPIAware())
    except Exception:
        return False


def real_user32():
    """ctypes.windll.user32 with 64-bit-safe handle signatures."""
    u = ctypes.windll.user32
    u.GetForegroundWindow.restype = ctypes.c_void_p
    u.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    u.MonitorFromWindow.restype = ctypes.c_void_p
    u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFOEXW)]
    return u


def rect_of(r):
    return {"left": r.left, "top": r.top,
            "width": r.right - r.left, "height": r.bottom - r.top}


def monitor_info(user32, hmon):
    """(device name without the \\\\.\\ prefix, rect) for one HMONITOR, or None."""
    info = MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(MONITORINFOEXW)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    return info.szDevice.replace("\\\\.\\", ""), rect_of(info.rcMonitor)


def list_monitors(user32=None, functype=None):
    """{"DISPLAY1": rect, ...} in EnumDisplayMonitors order; {} on failure.
    Names are Windows device names, stable across reboots for a given port."""
    try:
        user32 = user32 or real_user32()
        functype = functype or ctypes.WINFUNCTYPE
        proc_type = functype(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.POINTER(RECT), ctypes.c_ssize_t)
        handles = []

        def on_monitor(hmon, _hdc, _rect, _lparam):
            handles.append(hmon)
            return 1

        callback = proc_type(on_monitor)      # keep a reference while enumerating
        user32.EnumDisplayMonitors(None, None, callback, 0)
        mons = {}
        for i, hmon in enumerate(handles, start=1):
            found = monitor_info(user32, hmon)
            if found is not None:
                name, rect = found
                mons[name or f"screen{i}"] = rect
        return mons
    except Exception:
        return {}


def foreground_monitor_center(user32=None):
    """Centre of the monitor showing the foreground window (else the cursor's
    position), or None."""
    try:
        user32 = user32 or real_user32()
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            found = monitor_info(user32, hmon) if hmon else None
            if found is not None:
                r = found[1]
                return (r["left"] + r["width"] // 2, r["top"] + r["height"] // 2)
        pt = POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            return (pt.x, pt.y)
    except Exception:
        pass
    return None
