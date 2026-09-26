"""Settings screen: toggle rows with their enabled/disabled reasons, theme,
and the requests behind them."""
from dataclasses import dataclass

from ....model.settings_rules import MAX_NAME
from ....model.settings_rules import THEMES as THEME_IDS

THEMES = tuple((t, t.capitalize()) for t in THEME_IDS)
HOTKEY = "<ctrl>+<alt>+l"
TOGGLES = (
    ("login", "Start at login", "Restores the last mode when you sign in"),
    ("tray", "Keep running in the tray", "Closing the window leaves the light on"),
    ("hotkey", "Global shortcut", "Ctrl+Alt+L toggles the strip anywhere"),
    ("sunset", "Turn on at sunset", "Uses your time zone, no location needed"),
)
NO_TRAY = "This desktop has no system tray"
NO_SUNSET = "Needs your time zone to be set"
CONFIG_FOR = {"tray": "tray_on", "hotkey": "hotkey_on", "sunset": "sunset_on"}


@dataclass(frozen=True)
class Capability:
    """Whether a local feature works here, and why not if it doesn't."""
    available: bool = True
    reason: str = ""
    checked: bool = False


@dataclass(frozen=True)
class ToggleRow:
    id: str
    label: str
    desc: str
    checked: bool
    enabled: bool


def rows(status, login, hotkey, tray_available):
    """The four App toggles. `login` and `hotkey` are Capability values."""
    out = []
    for tid, label, desc in TOGGLES:
        if tid == "login":
            checked, enabled, why = login.checked, login.available, login.reason
        elif tid == "tray":
            checked, enabled = status.flag("tray_on") and tray_available, tray_available
            why = "" if tray_available else NO_TRAY
        elif tid == "hotkey":
            checked = status.flag("hotkey_on") and hotkey.available
            enabled, why = hotkey.available, hotkey.reason
        else:
            available = bool(status.raw.get("sunset_available"))
            checked, enabled = status.flag("sunset_on") and available, available
            why = "" if available else NO_SUNSET
        out.append(ToggleRow(tid, label, why if not enabled and why else desc, checked, enabled))
    return out


def toggle_request(toggle_id, value):
    """The daemon request for a toggle (None for start-at-login, which is local)."""
    key = CONFIG_FOR.get(toggle_id)
    return None if key is None else {"cmd": "config", "key": key, "value": bool(value)}


def theme_request(theme_id):
    return {"cmd": "config", "key": "theme", "value": theme_id}


def ceiling_request(value):
    return {"cmd": "config", "key": "max_brightness", "value": int(value)}


def rename_request(text, current):
    """config strip_name for an edited name, or None if empty/unchanged."""
    name = (text or "").strip()[:MAX_NAME]
    if not name or name == current:
        return None
    return {"cmd": "config", "key": "strip_name", "value": name}


def address_line(status):
    """(address, advertised name) for the Strip card."""
    return status.raw.get("address") or "Not set", status.raw.get("device_name") or ""
