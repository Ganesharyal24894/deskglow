"""X11 helpers for screen-mode: monitor geometry, focused-window monitor,
and fast average-color sampling via mss + numpy."""
import os
import re
import subprocess

import numpy as np

_MON_RE = re.compile(r"(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)")


def ensure_display_env():
    """Screen capture needs DISPLAY/XAUTHORITY. A systemd --user daemon may have
    started before the graphical session exported them; pull them from the user
    manager environment so xrandr/mss/Xlib can reach the X server."""
    need = [v for v in ("DISPLAY", "XAUTHORITY") if not os.environ.get(v)]
    if need:
        try:
            out = subprocess.run(["systemctl", "--user", "show-environment"],
                                 capture_output=True, text=True, timeout=5).stdout
            env = dict(line.split("=", 1) for line in out.splitlines()
                       if "=" in line)
            for v in need:
                if env.get(v):
                    os.environ[v] = env[v]
        except Exception:
            pass
    os.environ.setdefault("DISPLAY", ":0")


def get_monitors():
    """Return {name: {'left','top','width','height'}} from `xrandr --listmonitors`.

    Falls back to mss's own monitor list if xrandr yields nothing (e.g. names
    differ), so screen-mode still works with a single 'all-screens' region."""
    ensure_display_env()
    try:
        out = subprocess.run(["xrandr", "--listmonitors"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        out = ""
    mons = {}
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Monitors:"):
            continue
        name = line.split()[-1]
        m = _MON_RE.search(line)
        if m:
            w, h, x, y = (int(g) for g in m.groups())
            mons[name] = {"left": x, "top": y, "width": w, "height": h}
    if not mons:
        # xrandr gave nothing usable; fall back to mss's monitor list
        try:
            import mss
            with mss.mss() as sct:
                for i, mon in enumerate(sct.monitors[1:], start=1):
                    mons[f"screen{i}"] = {"left": mon["left"], "top": mon["top"],
                                          "width": mon["width"], "height": mon["height"]}
        except Exception:
            pass
    return mons


class ActiveWindow:
    """Tracks which monitor the focused window (or mouse) is on, via Xlib."""

    def __init__(self):
        self._d = None
        try:
            ensure_display_env()
            from Xlib import display, X
            self._X = X
            self._d = display.Display()
            self._root = self._d.screen().root
            self._atom = self._d.intern_atom("_NET_ACTIVE_WINDOW")
        except Exception:
            self._d = None

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


def pick_monitor(monitors, point):
    """Return the rect of the monitor containing `point`, else the first monitor."""
    if point is not None:
        x, y = point
        for rect in monitors.values():
            if (rect["left"] <= x < rect["left"] + rect["width"]
                    and rect["top"] <= y < rect["top"] + rect["height"]):
                return rect
    return next(iter(monitors.values()))


def bounding_rect(monitors):
    """Rect covering all monitors (for 'both')."""
    left = min(r["left"] for r in monitors.values())
    top = min(r["top"] for r in monitors.values())
    right = max(r["left"] + r["width"] for r in monitors.values())
    bottom = max(r["top"] + r["height"] for r in monitors.values())
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}


STYLES = ("average", "vivid", "dominant", "edge")


class Sampler:
    """Grabs a screen rect and reduces it to one RGB by the chosen `style`.

    mss lives in one thread (created lazily). All styles operate on a
    downsampled copy for speed.
    """

    def __init__(self):
        self._sct = None

    def _ensure(self):
        if self._sct is None:
            import mss
            self._sct = mss.mss()

    def _grab(self, rect):
        self._ensure()
        img = self._sct.grab(rect)
        arr = np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)
        step = max(1, img.width // 220)  # ~220px wide sample grid
        return arr[::step, ::step].astype(np.float32)

    def sample(self, rect, style="average"):
        arr = self._grab(rect)
        if style == "edge":
            return self._edge(arr)
        flat = arr.reshape(-1, 3)
        if style == "vivid":
            return self._vivid(flat)
        if style == "dominant":
            return self._dominant(flat)
        return _tuple(flat.mean(axis=0))  # average

    @staticmethod
    def _edge(arr):
        h, w, _ = arr.shape
        b = max(2, h // 12)
        bands = [arr[:b], arr[-b:], arr[:, :b], arr[:, -b:]]
        border = np.concatenate([x.reshape(-1, 3) for x in bands])
        return _tuple(border.mean(axis=0))

    @staticmethod
    def _hsv_parts(flat):
        mx = flat.max(axis=1)
        mn = flat.min(axis=1)
        v = mx / 255.0
        s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
        return s, v

    def _vivid(self, flat):
        """Saturation-weighted average: grey pixels contribute ~nothing (s^3),
        so even a small colorful region drives the result. Robust when the
        vivid area is only a few percent of the screen."""
        s, v = self._hsv_parts(flat)
        weight = (s ** 3) * v
        total = weight.sum()
        if weight.max() < 0.06 or total < 1e-6:   # basically greyscale
            return _tuple(flat.mean(axis=0))
        col = (flat * weight[:, None]).sum(axis=0) / total
        return _boost_saturation(col, 1.3)

    def _dominant(self, flat):
        """Most common hue (quantized), weighted by saturation*brightness,
        rendered at high saturation. More stable/punchier than 'vivid'."""
        s, v = self._hsv_parts(flat)
        weight = (s ** 1.5) * v
        if weight.max() < 0.06:
            return _tuple(flat.mean(axis=0))
        # quantize each channel to 6 levels -> 216 buckets, weighted histogram
        q = np.clip((flat / 256.0 * 6).astype(np.int32), 0, 5)
        keys = q[:, 0] * 36 + q[:, 1] * 6 + q[:, 2]
        totals = np.bincount(keys, weights=weight, minlength=216)
        best = int(totals.argmax())
        mask = keys == best
        col = flat[mask].mean(axis=0)
        return _boost_saturation(col, 1.5)


def _tuple(a):
    return (float(a[0]), float(a[1]), float(a[2]))


def _boost_saturation(col, factor):
    import colorsys
    r, g, b = (float(c) / 255.0 for c in col)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * factor), v)
    return (r * 255.0, g * 255.0, b * 255.0)
