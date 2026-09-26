"""The `status` reply: the daemon's live mode, the strip, and the settings."""
from ..model.color import to_hex

# Settings echoed verbatim in every status reply.
ECHOED = ("screen_monitor", "screen_style", "max_brightness", "brightness",
          "favourites", "sunset_on", "audio_sensitivity", "hotkey_on", "tray_on",
          "theme", "focus_timer")


def _hex(rgb):
    try:
        return to_hex(rgb) if rgb is not None and len(rgb) == 3 else None
    except (TypeError, ValueError):
        return None


def current_colour(d):
    """What the strip shows as #RRGGBB: a solid mode's colour, a live mode's
    latest colour, None when off or running a built-in effect."""
    if d.mode_name in ("off", "pattern"):
        return None
    if d.mode_name == "solid":
        return _hex(d.mode_args.get("rgb"))
    ctx = getattr(d, "mode_ctx", None)
    return _hex(ctx.shown) if ctx is not None else None


def _live(d):
    """Readings the running mode publishes (screen colour/fps, level, timer)."""
    ctx = getattr(d, "mode_ctx", None)
    tel = dict(ctx.telemetry) if ctx is not None else {}
    screen = audio = focus = None
    if d.mode_name == "screen" and "screen_color" in tel:
        screen = {"color": _hex(tel["screen_color"]),
                  "fps": round(float(tel.get("screen_fps", 0.0)), 1)}
    if d.mode_name == "audio":
        audio = round(float(tel.get("audio_level", 0.0)), 3)
    if d.mode_name == "pomodoro" and isinstance(tel.get("focus"), dict):
        focus = dict(tel["focus"])
    return screen, audio, focus


def build_status(d):
    screen, audio, focus = _live(d)
    reply = {"ok": True, "mode": d.mode_name, "desc": d.mode_desc,
             "args": d.mode_args,
             "connected": d.device.connected,
             "configured": bool(d.device.address),
             "address": d.device.address,
             "device_name": d.settings.get_device_name(),
             "name": d.state.get("strip_name"),
             "color": current_colour(d),
             "last_solid": _hex(d.state.get("last_solid")),
             "rssi": getattr(d, "rssi", None),
             "sunset_available": d.sunset.available(),
             "screen": screen, "audio_level": audio, "focus": focus}
    for key in ECHOED:
        reply[key] = d.state.get(key)
    return reply
