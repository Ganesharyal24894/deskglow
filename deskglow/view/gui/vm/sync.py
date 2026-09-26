"""Sync screen: the monitor diagram, target chips, colour styles, the level
meter, and the requests behind them."""
from dataclasses import dataclass

from ....model.settings import SCREEN_STYLES
from .home import back_to_colour

STYLE_DESCS = {
    "average": "Mean colour of the whole screen. Calm and muted.",
    "vivid": "Favours the most colourful pixels, so small bright areas still show.",
    "dominant": "The most common hue, rendered clean and punchy.",
    "edge": "Only the screen border, like an ambilight.",
}
STYLES = tuple((s, s.capitalize()) for s in SCREEN_STYLES)
SOURCES = (("system", "System sound"), ("mic", "Microphone"))
METER_BARS = 18
BOX_HEIGHT = 96          # the tallest monitor in the diagram, px
WIDTH_FACTOR = 0.88      # the design draws screens a little narrower than true


@dataclass(frozen=True)
class MonitorBox:
    name: str
    width: int
    height: int
    resolution: str


def ordered(monitors):
    """Monitor names left to right (then top to bottom)."""
    return sorted(monitors, key=lambda n: (monitors[n].get("left", 0), monitors[n].get("top", 0)))


def boxes(monitors, max_height=BOX_HEIGHT):
    """Scaled boxes for the diagram, in left-to-right order."""
    if not monitors:
        return []
    tallest = max(m["height"] for m in monitors.values()) or 1
    k = max_height / tallest
    return [MonitorBox(n, round(monitors[n]["width"] * k * WIDTH_FACTOR),
                       round(monitors[n]["height"] * k),
                       f"{monitors[n]['width']} × {monitors[n]['height']}")
            for n in ordered(monitors)]


def primary(monitors):
    """The monitor at the desktop origin (else the leftmost): the one the
    diagram lights for "Focused window", which follows your focus."""
    for n in ordered(monitors):
        if monitors[n].get("left", 0) == 0 and monitors[n].get("top", 0) == 0:
            return n
    names = ordered(monitors)
    return names[0] if names else None


def targets(monitors):
    return [("focus", "Focused window"), ("both", "All screens")] + [(n, n) for n in ordered(monitors)]


def lit(target, name, monitors):
    return target in (name, "both") or (target == "focus" and name == primary(monitors))


def readout(status):
    """("#RRGGBB", "15 fps") while screen sync runs, else None."""
    live = status.raw.get("screen")
    if status.mode != "screen" or not isinstance(live, dict) or not live.get("color"):
        return None
    return live["color"], f"{round(live.get('fps') or 0):d} fps"


class Meter:
    """The last METER_BARS audio levels, newest on the right."""

    def __init__(self, bars=METER_BARS):
        self.levels = [0.0] * bars

    def push(self, level):
        level = max(0.0, min(1.0, float(level or 0.0)))
        self.levels = self.levels[1:] + [level]

    def reset(self):
        self.levels = [0.0] * len(self.levels)

    def heights(self, floor=0.06):
        """Bar heights as fractions of the well (never zero, so bars stay visible)."""
        return [max(floor, lv) for lv in self.levels]


def set_target(target):
    return {"cmd": "config", "key": "screen_monitor", "value": target}


def set_style(style):
    return {"cmd": "config", "key": "screen_style", "value": style}


def set_sensitivity(value):
    return {"cmd": "config", "key": "audio_sensitivity", "value": int(value)}


def screen_button(status, style):
    """(label, request) for the screen card's main button."""
    if status.mode == "screen":
        return "Stop screen sync", back_to_colour(status)
    return "Start screen sync", {"cmd": "set_mode", "mode": "screen", "args": {"style": style}}


def music_button(status, source):
    if status.mode == "audio":
        return "Stop music sync", back_to_colour(status)
    return "Start music sync", {"cmd": "set_mode", "mode": "audio", "args": {"source": source}}


def source_change(status, source):
    """Changing the input while music sync runs restarts it on the new one."""
    if status.mode == "audio" and status.args.get("source") != source:
        return {"cmd": "set_mode", "mode": "audio", "args": {"source": source}}
    return None
