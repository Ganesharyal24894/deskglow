"""X11 session helpers: recover DISPLAY for a service, list monitor geometry."""
import os
import re
import subprocess

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


def parse_xrandr(out):
    """{name: rect} from `xrandr --listmonitors` output (junk lines skipped)."""
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
    return mons


def get_monitors():
    """Return {name: {'left','top','width','height'}} from `xrandr --listmonitors`.

    Falls back to mss's own monitor list if xrandr yields nothing (e.g. names
    differ), so screen-mode still works; {} if no display is reachable."""
    ensure_display_env()
    try:
        out = subprocess.run(["xrandr", "--listmonitors"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        out = ""
    mons = parse_xrandr(out)
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
