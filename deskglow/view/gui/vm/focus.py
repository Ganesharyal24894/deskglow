"""Focus screen: the ring timer, its buttons, the steppers and the legend."""
import math
from dataclasses import dataclass

from ....model.settings_rules import FOCUS_LIMITS
from .home import back_to_colour
from .status import PHASE_COLOURS

# key, label, step, unit
STEPPERS = (("work", "Focus", 5, " min"), ("break", "Break", 1, " min"), ("rounds", "Rounds", 1, ""))
CUES = (("Focus", "Steady calm cyan", PHASE_COLOURS["focus"], 1.0),
        ("Break", "Soft green", PHASE_COLOURS["break"], 1.0),
        ("Last minute", "Gently breathes", "focus_label", 0.55),   # palette token
        ("Done", "Settles on lavender", PHASE_COLOURS["done"], 1.0))
PHASE_LABELS = {"focus": "FOCUS", "break": "BREAK", "done": "DONE"}


@dataclass(frozen=True)
class Ring:
    fraction: float      # how much of the ring is lit (time remaining)
    time_text: str
    label: str
    round_text: str
    colour: str
    running: bool
    paused: bool


def clock(seconds):
    s = max(0, math.ceil(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def ring(status):
    timer = status.raw.get("focus")
    if status.mode == "pomodoro" and isinstance(timer, dict):
        total = float(timer.get("total") or 0.0)
        remaining = float(timer.get("remaining") or 0.0)
        phase = timer.get("phase", "focus")
        frac = remaining / total if total > 0 else 0.0
        return Ring(max(0.0, min(1.0, frac)), clock(remaining), PHASE_LABELS.get(phase, "FOCUS"),
                    f"Round {timer.get('round', 1)} of {timer.get('rounds', 1)}",
                    PHASE_COLOURS.get(phase, PHASE_COLOURS["focus"]), True,
                    bool(timer.get("paused")))
    t = status.focus_timer
    return Ring(1.0, clock(t["work"] * 60), "FOCUS", f"Round 1 of {t['rounds']}",
                PHASE_COLOURS["focus"], False, False)


def step(timer, key, direction):
    """A new focus_timer with `key` moved one step up (+1) or down (-1)."""
    size = next(s for k, _label, s, _u in STEPPERS if k == key)
    lo, hi = FOCUS_LIMITS[key]
    value = timer[key] + direction * size
    if key == "work" and direction < 0 and timer[key] <= size:
        value = timer[key] - 1          # below one step, go minute by minute
    out = dict(timer)
    out[key] = max(lo, min(hi, value))
    return out


def value_text(key, value):
    unit = next(u for k, _label, _s, u in STEPPERS if k == key)
    return f"{value}{unit}"


def save_timer(timer):
    return {"cmd": "config", "key": "focus_timer", "value": dict(timer)}


def primary_button(status):
    """(label, request) for the accent button: Start, Pause or Resume."""
    r = ring(status)
    if not r.running:
        t = status.focus_timer
        return "Start", {"cmd": "set_mode", "mode": "pomodoro",
                         "args": {"work": t["work"], "break": t["break"], "rounds": t["rounds"]}}
    if r.paused:
        return "Resume", {"cmd": "focus_pause", "paused": False}
    return "Pause", {"cmd": "focus_pause", "paused": True}


def stop_request(status):
    return back_to_colour(status) if status.mode == "pomodoro" else None
