"""Mode registry: build a Mode instance from a name + args dict."""
from .base import Mode, ModeContext
from .solid import Solid
from .screen import Screen
from .calm import Calm
from .patterns import Patterns, pattern_names
from .circadian import Circadian
from .pomodoro import Pomodoro
from .audio import Audio

MODE_NAMES = ["solid", "screen", "calm", "pattern", "circadian", "pomodoro", "audio"]


def build(name, args):
    """Return a Mode for `name` with `args` (dict), or raise ValueError."""
    n = (name or "").lower()
    args = args or {}
    if n == "solid":
        return Solid(args.get("rgb", [255, 180, 110]))
    if n == "screen":
        return Screen()
    if n == "calm":
        return Calm()
    if n == "pattern":
        return Patterns(args.get("name", "fade-colors"), args.get("speed", 50))
    if n == "circadian":
        return Circadian()
    if n == "pomodoro":
        return Pomodoro(args.get("work", 25), args.get("break", 5),
                        args.get("rounds", 4))
    if n == "audio":
        return Audio(args.get("rgb"), args.get("target"),
                     args.get("source", "system"))
    raise ValueError(f"unknown mode {name!r}")


__all__ = ["Mode", "ModeContext", "build", "MODE_NAMES", "pattern_names"]
