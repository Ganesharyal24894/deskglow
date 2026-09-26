"""What the strip sees: renders light commands into frame bytes from a preset.

Every value is truncated to an int and clamped to the preset's range for its
placeholder (never wrapped modulo 256), so the output is always a well-formed
frame the controller recognises.
"""
from ..model.presets import get_preset


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


class StripEncoder:
    """A FrameEncoder for one controller preset."""

    def __init__(self, preset=None):
        self.preset = preset or get_preset()

    def render(self, frame, **values):
        """Fill the named frame template's placeholders with clamped values."""
        out = []
        for tok in self.preset.frames[frame]:
            if isinstance(tok, str):
                lo, hi = self.preset.ranges[tok]
                tok = _clamp(values[tok], lo, hi)
            out.append(tok)
        return bytes(out)

    def power(self, on):
        return self.render("power_on" if on else "power_off")

    def color(self, r, g, b):
        return self.render("color", r=r, g=g, b=b)

    def brightness(self, pct):
        return self.render("brightness", brightness=pct)

    def effect(self, effect_id):
        return self.render("effect", effect=effect_id)

    def speed(self, pct):
        return self.render("speed", speed=pct)

    def status_query(self):
        # Some firmwares reply on the notify characteristic; harmless if ignored.
        return self.render("status_query")
