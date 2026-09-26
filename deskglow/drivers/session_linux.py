"""Which kind of graphical session a Linux process belongs to (X11 or Wayland)."""
import subprocess


def systemd_user_env(run=subprocess.run):
    """The systemd user manager's environment ({} if unavailable). A daemon
    started before the desktop exported its variables can still find them here."""
    try:
        out = run(["systemctl", "--user", "show-environment"],
                  capture_output=True, text=True, timeout=5).stdout
        return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    except Exception:
        return {}


def _says_wayland(env):
    if env.get("WAYLAND_DISPLAY") or env.get("XDG_SESSION_TYPE") == "wayland":
        return True
    if env.get("DISPLAY") or env.get("XDG_SESSION_TYPE") == "x11":
        return False
    return None


def is_wayland(env, user_env=systemd_user_env):
    """True on a Wayland session. XWayland also sets DISPLAY there, but X11
    capture would only see XWayland windows, so Wayland wins."""
    verdict = _says_wayland(env)
    if verdict is None:
        verdict = _says_wayland(user_env())
    return bool(verdict)
