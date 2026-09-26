"""Mode registry: build a Mode instance from a name + args dict.

Modes with heavy or optional dependencies (screen and audio need numpy, plus
their capture drivers) are imported lazily inside build(), so a core install
without those extras can still run the daemon, the CLI and every other mode.
"""
from .base import Mode, ModeContext
from .calm import Calm
from .circadian import Circadian
from .patterns import Patterns, pattern_names
from .pomodoro import Pomodoro
from .solid import Solid

MODE_NAMES = ["solid", "screen", "calm", "pattern", "circadian", "pomodoro", "audio"]

# mode name -> the pip extra that provides its dependencies
EXTRAS = {"screen": "screen", "audio": "audio"}


class ModeUnavailable(ValueError):
    """A mode exists but its optional dependencies are not installed."""


def _load(name, importer):
    """Import an optional mode, turning a missing dependency into clear advice."""
    try:
        return importer()
    except ImportError as e:
        raise ModeUnavailable(
            f"{name} mode needs extra packages: pip install 'deskglow[{EXTRAS[name]}]' "
            f"({e})") from e


def build(name, args, preset=None):
    """Return a Mode for `name` with `args` (dict), or raise ValueError.

    `preset` is the controller preset (effect table) for pattern mode; the
    default preset is used when omitted."""
    n = (name or "").lower()
    args = args or {}
    if n == "solid":
        return Solid(args.get("rgb", [255, 180, 110]))
    if n == "screen":
        def _screen():
            from .screen import Screen
            return Screen()
        return _load("screen", _screen)
    if n == "calm":
        return Calm()
    if n == "pattern":
        return Patterns(args.get("name"), args.get("speed", 50), preset=preset)
    if n == "circadian":
        return Circadian()
    if n == "pomodoro":
        return Pomodoro(args.get("work", 25), args.get("break", 5),
                        args.get("rounds", 4))
    if n == "audio":
        def _audio():
            from .audio import Audio
            return Audio(args.get("rgb"), args.get("target"),
                         args.get("source", "system"))
        return _load("audio", _audio)
    raise ValueError(f"unknown mode {name!r}")


__all__ = ["EXTRAS", "MODE_NAMES", "Mode", "ModeContext", "ModeUnavailable",
           "build", "pattern_names"]
