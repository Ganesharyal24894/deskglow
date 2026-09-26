"""The tray quick panel: its status line and quick-mode buttons."""
from .status import MODE_LABELS

QUICK = (("screen", "Screen sync"), ("audio", "Music"), ("calm", "Calm"), ("effects", "Effects"))


def status_line(status):
    """e.g. "Solid colour · connected" or "Off · standby"."""
    if not status.reachable:
        return "Service not running"
    if not status.on:
        what = "Off"
    elif status.mode == "solid":
        what = "Solid colour"
    else:
        what = MODE_LABELS.get(status.mode, status.mode.capitalize())
    return f"{what} · {status.connection()[0].lower()}"


def menu_power_label(status):
    return "Turn off" if status.on else "Turn on"
