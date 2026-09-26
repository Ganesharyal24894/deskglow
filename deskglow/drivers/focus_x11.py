"""FocusTracker for X11 via python-xlib: the focused window's centre."""
from . import x11_display


class XlibFocusTracker:
    """Tracks where the focused window (or mouse) is. Degrades to None."""

    def __init__(self, display_factory=None):
        self._d = None
        try:
            x11_display.ensure_display_env()
            from Xlib import X, display
            self._X = X
            self._d = (display_factory or display.Display)()
            self._root = self._d.screen().root
            self._atom = self._d.intern_atom("_NET_ACTIVE_WINDOW")
        except Exception:
            self._d = None

    def close(self):
        """Release the X connection (screen mode opens one per start)."""
        d, self._d = self._d, None
        if d is not None:
            try:
                d.close()
            except Exception:
                pass

    def center(self):
        """Return (x, y) of the focused window center, or the mouse if unknown."""
        if self._d is None:
            return None
        try:
            prop = self._root.get_full_property(self._atom, self._X.AnyPropertyType)
            if prop and prop.value:
                wid = prop.value[0]
                if wid:
                    win = self._d.create_resource_object("window", wid)
                    g = win.get_geometry()
                    t = win.translate_coords(self._root, 0, 0)
                    return (t.x + g.width // 2, t.y + g.height // 2)
        except Exception:
            pass
        try:
            p = self._root.query_pointer()
            return (p.root_x, p.root_y)
        except Exception:
            return None
