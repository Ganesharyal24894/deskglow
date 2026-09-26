"""Validation rules for each client-settable setting. Pure functions.

Each rule takes the raw value from a request and returns the value to store,
or raises ValueError with a message a person can act on.
"""
import re

SCREEN_STYLES = ("average", "vivid", "dominant", "edge")
THEMES = ("system", "dark", "light")
MAX_FAVOURITES = 8
MAX_NAME = 40
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# A BLE MAC (Linux/Windows) or a CoreBluetooth peripheral UUID (macOS).
_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")
_UUID_RE = re.compile(r"^[0-9A-Fa-f]{8}(-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}$")
FOCUS_LIMITS = {"work": (1, 180), "break": (1, 60), "rounds": (1, 12)}


def _number(key, value, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number {lo}-{hi}, got {value!r}")
    return max(lo, min(hi, int(round(value))))


def _flag(key):
    def rule(value):
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false, got {value!r}")
        return value
    return rule


def hex_colour(value):
    """'#rrggbb' in any case -> '#RRGGBB', else ValueError."""
    if not isinstance(value, str) or not HEX_RE.match(value.strip()):
        raise ValueError(f"colour must look like #RRGGBB, got {value!r}")
    return value.strip().upper()


def address(value):
    """A strip address: MAC 'AA:BB:CC:DD:EE:FF' or a macOS UUID, normalised."""
    v = value.strip() if isinstance(value, str) else ""
    if _MAC_RE.match(v) or _UUID_RE.match(v):
        return v.upper()
    raise ValueError(f"not a Bluetooth address: {value!r} (expected AA:BB:CC:DD:EE:FF)")


def _screen_style(value):
    if value not in SCREEN_STYLES:
        raise ValueError(f"screen_style must be one of {', '.join(SCREEN_STYLES)}")
    return value


def _screen_monitor(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("screen_monitor must be 'focus', 'both', or an output name")
    return value.strip()


def _strip_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("strip_name must be a non-empty string")
    v = value.strip()
    if len(v) > MAX_NAME:
        raise ValueError(f"strip_name must be at most {MAX_NAME} characters")
    return v


def _favourites(value):
    if not isinstance(value, list):
        raise ValueError("favourites must be a list of #RRGGBB colours")
    out = []
    for item in value:
        c = hex_colour(item)
        if c not in out:
            out.append(c)
    if len(out) > MAX_FAVOURITES:
        raise ValueError(f"at most {MAX_FAVOURITES} favourites")
    return out


def _theme(value):
    if value not in THEMES:
        raise ValueError(f"theme must be one of {', '.join(THEMES)}")
    return value


def _focus_timer(value):
    if not isinstance(value, dict):
        raise ValueError("focus_timer must be {work, break, rounds}")
    out = {}
    for k, (lo, hi) in FOCUS_LIMITS.items():
        if k not in value:
            raise ValueError(f"focus_timer is missing {k!r}")
        out[k] = _number(f"focus_timer.{k}", value[k], lo, hi)
    return out


RULES = {
    "max_brightness": lambda v: _number("max_brightness", v, 0, 100),
    "brightness": lambda v: _number("brightness", v, 0, 100),
    "audio_sensitivity": lambda v: _number("audio_sensitivity", v, 1, 100),
    "screen_style": _screen_style,
    "screen_monitor": _screen_monitor,
    "strip_name": _strip_name,
    "favourites": _favourites,
    "sunset_on": _flag("sunset_on"),
    "hotkey_on": _flag("hotkey_on"),
    "tray_on": _flag("tray_on"),
    "theme": _theme,
    "focus_timer": _focus_timer,
}


def add_favourite(favs, colour):
    """Favourites with `colour` first (moved if present), capped at the maximum."""
    c = hex_colour(colour)
    rest = [f for f in favs if f != c]
    return ([c] + rest)[:MAX_FAVOURITES]


def remove_favourite(favs, colour):
    c = hex_colour(colour)
    return [f for f in favs if f != c]
