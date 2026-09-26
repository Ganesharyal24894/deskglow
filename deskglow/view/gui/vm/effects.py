"""Effects screen: a tile per built-in effect of the strip's preset, with a
gradient preview derived from the effect's name."""
from dataclasses import dataclass

COLOURS = {"red": "#FF3B30", "green": "#34C759", "blue": "#1E7BFF", "yellow": "#FFD60A",
           "cyan": "#32D7F0", "magenta": "#E040FB", "white": "fx_white"}   # white: a palette token
SEVEN = [COLOURS[c] for c in ("red", "yellow", "green", "cyan", "blue", "magenta", "white")]
RGB = [COLOURS["red"], COLOURS["green"], COLOURS["blue"]]
FILTERS = (("all", "All"), ("fade", "Fade"), ("jump", "Jump"), ("blink", "Blink"))
DARK = "fx_dark"      # palette token: the dark ends of a single-colour fade
GAP = "blink_gap"     # palette token: the dark gaps of a blink
EDGE = 0.0005         # makes a hard stop out of two gradient stops


@dataclass(frozen=True)
class Effect:
    id: str
    kind: str          # fade | jump | blink
    label: str
    stops: tuple       # ((position 0..1, "#RRGGBB" or a palette token), ...)


def hard(cols):
    n = len(cols)
    out = []
    for i, c in enumerate(cols):
        out += [(i / n, c), ((i + 1) / n - EDGE, c)]
    return tuple(out)


def soft(cols):
    n = len(cols) - 1
    return tuple((i / n, c) for i, c in enumerate(cols))


def blink(cols):
    w = 1.0 / len(cols)
    out = []
    for i, c in enumerate(cols):
        a = i * w
        out += [(a, c), (a + w * 0.55 - EDGE, c), (a + w * 0.55, GAP), (a + w - EDGE, GAP)]
    return tuple(out)


def describe(effect_id):
    """Label and preview for a preset effect name like 'fade-red-blue'."""
    kind, _, rest = effect_id.partition("-")
    parts = rest.split("-") if rest else []
    if parts == ["rgb"]:
        cols, what = RGB, "RGB"
    elif parts == ["colors"]:
        cols, what = SEVEN, "7 colours"
    else:
        cols = [COLOURS.get(p, "#808080") for p in parts] or ["#808080"]
        what = " & ".join(p.capitalize() for p in parts) or effect_id
    if kind == "jump":
        stops = hard(cols)
    elif kind == "blink":
        stops = blink(cols if len(cols) > 1 else cols * 4)
    else:
        kind = "fade"          # unknown prefixes preview as a fade
        if len(cols) == 1:
            stops = soft([DARK, cols[0], DARK])
        elif len(parts) == 2:
            stops = soft([cols[0], cols[1], cols[0]])
        else:
            stops = soft(cols)
    return Effect(effect_id, kind, f"{kind.capitalize()} · {what}", stops)


def effects(names):
    return [describe(n) for n in names]


def visible(all_effects, filter_id):
    return [e for e in all_effects if filter_id == "all" or e.kind == filter_id]


def play(effect_id, speed):
    return {"cmd": "set_mode", "mode": "pattern",
            "args": {"name": effect_id, "speed": max(1, min(100, int(speed)))}}
