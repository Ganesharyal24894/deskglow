"""The daemon's `status` reply, read the way every screen needs it."""
from ....controller.modes.pomodoro import BREAK_COLOR, DONE_COLOR, FOCUS_COLOR
from ....model.color import from_hex, to_hex
from ....model.settings import DEFAULT_FAVOURITES, DEFAULTS
from ..theme import DEFAULT_ACCENT

SWATCH_NAMES = {"#FFB46E": "Warm white", "#FFFFFF": "White", "#FF3B30": "Red",
                "#FF7A1A": "Orange", "#3DDC97": "Mint", "#00B8C7": "Teal",
                "#5B8CFF": "Blue", "#B35CFF": "Violet", "#FF4D8D": "Pink"}
MODE_LABELS = {"screen": "Screen sync", "audio": "Music", "calm": "Calm",
               "circadian": "Circadian", "pattern": "Effects", "pomodoro": "Focus"}
PHASE_COLOURS = {"focus": to_hex(FOCUS_COLOR), "break": to_hex(BREAK_COLOR),
                 "done": to_hex(DONE_COLOR)}


def colour_name(hex_value):
    return SWATCH_NAMES.get((hex_value or "").upper(), "Custom colour")


def glow_alpha(on, brightness):
    """How strongly the accent glows (the design's 0.25 + 0.6 x level)."""
    return 0.25 + 0.6 * max(0, min(100, brightness)) / 100.0 if on else 0.0


def rgb(hex_value):
    return from_hex(hex_value)


class StatusView:
    """Read-only accessors over one status reply (a dict)."""

    def __init__(self, reply=None):
        self.raw = reply if isinstance(reply, dict) else {}
        self.reachable = bool(self.raw.get("ok"))

    def get(self, key, default=None):
        value = self.raw.get(key)
        return default if value is None else value

    @property
    def mode(self):
        return self.get("mode", "off")

    @property
    def on(self):
        return self.reachable and self.mode != "off"

    @property
    def configured(self):
        return bool(self.raw.get("configured"))

    @property
    def brightness(self):
        return int(self.get("brightness", 100))

    @property
    def max_brightness(self):
        return int(self.get("max_brightness", 100))

    @property
    def name(self):
        return self.get("name", DEFAULTS["strip_name"])

    @property
    def favourites(self):
        favs = self.raw.get("favourites")
        return list(favs) if isinstance(favs, list) else list(DEFAULT_FAVOURITES)

    @property
    def focus_timer(self):
        t = self.raw.get("focus_timer")
        return dict(t) if isinstance(t, dict) else dict(DEFAULTS["focus_timer"])

    @property
    def args(self):
        a = self.raw.get("args")
        return a if isinstance(a, dict) else {}

    @property
    def last_solid(self):
        return self.get("last_solid", DEFAULT_ACCENT)

    @property
    def accent(self):
        """The app's accent: the colour the strip is (or was last) set to."""
        if self.mode == "solid" and self.raw.get("color"):
            return self.raw["color"]
        if self.mode == "pomodoro":
            phase = (self.raw.get("focus") or {}).get("phase", "focus")
            return PHASE_COLOURS.get(phase, PHASE_COLOURS["focus"])
        return self.last_solid

    @property
    def glow(self):
        return glow_alpha(self.on, self.brightness)

    def mode_label(self):
        if self.mode == "solid":
            return colour_name(self.raw.get("color"))
        return MODE_LABELS.get(self.mode, self.mode.capitalize())

    def state_text(self):
        if not self.reachable:
            return "Can't reach the Deskglow service"
        if not self.on:
            return "Off"
        return f"{self.mode_label()} · {self.brightness}%"

    def connection(self):
        """(text, palette token for the dot) for the sidebar device card."""
        if not self.reachable:
            return "Service not running", "idle"
        if not self.configured:
            return "No strip set up", "idle"
        if self.raw.get("connected"):
            return "Connected", "ok"
        if self.mode == "off":
            return "Standby", "idle"
        return "Connecting…", "warn"

    def rssi_text(self):
        rssi = self.raw.get("rssi")
        return f"{rssi} dBm" if isinstance(rssi, int) and self.raw.get("connected") else ""

    def flag(self, key):
        return bool(self.raw.get(key, DEFAULTS.get(key)))
