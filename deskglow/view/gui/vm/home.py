"""Home screen: swatches, mode tiles and the requests they send."""
from dataclasses import dataclass

from ....model.color import from_hex
from ....model.presets import get_preset
from .status import colour_name


@dataclass(frozen=True)
class Tile:
    id: str
    label: str
    desc: str
    icon: str       # key into view.gui.icons


MODE_TILES = (
    Tile("screen", "Screen sync", "Match what is on your monitor", "SYNC"),
    Tile("audio", "Music", "Pulse to system sound or mic", "MUSIC"),
    Tile("calm", "Calm", "Soft colours drift and breathe", "CALM"),
    Tile("circadian", "Circadian", "White that warms after sunset", "CIRCADIAN"),
    Tile("effects", "Effects", "Built-in jump, fade and blink", "EFFECTS"),
    Tile("focus", "Focus", "Pomodoro timer in light", "FOCUS"),
)
# daemon mode -> the tile that shows it as active
TILE_FOR_MODE = {"screen": "screen", "audio": "audio", "calm": "calm",
                 "circadian": "circadian", "pattern": "effects", "pomodoro": "focus"}


@dataclass(frozen=True)
class Swatch:
    colour: str
    name: str
    selected: bool


def swatches(status):
    """The favourites grid (8 cells); the strip's solid colour is selected."""
    current = status.raw.get("color") if status.mode == "solid" and status.on else None
    return [Swatch(c, colour_name(c), current is not None and c == current.upper())
            for c in status.favourites]


def active_tile(status):
    return TILE_FOR_MODE.get(status.mode) if status.on else None


def solid(hex_value):
    return {"cmd": "set_mode", "mode": "solid", "args": {"rgb": list(from_hex(hex_value))}}


def power(status):
    return {"cmd": "off"} if status.on else {"cmd": "on"}


def brightness(value):
    return {"cmd": "config", "key": "brightness", "value": int(value)}


def save_favourite(hex_value):
    return {"cmd": "favourite_add", "color": hex_value}


def remove_favourite(hex_value):
    return {"cmd": "favourite_remove", "color": hex_value}


def last_effect(status, remembered=None):
    """The effect the Effects tile (re)starts: the running one, else the last
    one picked in this session, else the preset's default."""
    if status.mode == "pattern" and status.args.get("name"):
        return status.args["name"], int(status.args.get("speed", 50))
    if remembered:
        return remembered
    return get_preset().default_effect, 50


def tile_request(tile_id, status, remembered_effect=None):
    """The request a Modes tile sends."""
    if tile_id in ("screen", "calm", "circadian"):
        return {"cmd": "set_mode", "mode": tile_id, "args": {}}
    if tile_id == "audio":
        return {"cmd": "set_mode", "mode": "audio", "args": {"source": "system"}}
    if tile_id == "effects":
        name, speed = last_effect(status, remembered_effect)
        return {"cmd": "set_mode", "mode": "pattern", "args": {"name": name, "speed": speed}}
    if tile_id == "focus":
        t = status.focus_timer
        return {"cmd": "set_mode", "mode": "pomodoro",
                "args": {"work": t["work"], "break": t["break"], "rounds": t["rounds"]}}
    raise ValueError(f"unknown tile {tile_id!r}")


def back_to_colour(status):
    """What "Stop" (timer, sync) returns to: the last solid colour."""
    return solid(status.last_solid)
