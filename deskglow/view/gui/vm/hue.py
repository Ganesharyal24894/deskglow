"""The hue ring's geometry: the design's conic gradient, angle <-> colour.

Angles are degrees clockwise from 12 o'clock, like CSS conic-gradient."""
import colorsys
import math

from ....model.color import from_hex, to_hex

CONIC = ("#FF3B30", "#FFCC00", "#34C759", "#00C7BE", "#007AFF", "#AF52DE", "#FF2D55", "#FF3B30")
OUTER = 64.0     # ring radius
INNER = 42.0     # the hole's radius
MARKER = 53.0    # where the marker sits (middle of the band)


def _hue(hex_value):
    r, g, b = (c / 255.0 for c in from_hex(hex_value))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360.0


_STEP = 360.0 / (len(CONIC) - 1)
# hue of each stop, made increasing so it can be interpolated
_HUES = []
for _c in CONIC:
    h = _hue(_c)
    while _HUES and h < _HUES[-1]:
        h += 360.0
    _HUES.append(h)


def colour_at(angle):
    """The gradient's colour at `angle` degrees."""
    a = angle % 360.0
    i = min(int(a // _STEP), len(CONIC) - 2)
    t = (a - i * _STEP) / _STEP
    c0, c1 = from_hex(CONIC[i]), from_hex(CONIC[i + 1])
    return to_hex(tuple(c0[k] + (c1[k] - c0[k]) * t for k in range(3)))


def angle_for(hex_value):
    """Where on the ring a colour's hue sits (for the marker)."""
    h = _hue(hex_value)
    if h < _HUES[0]:
        h += 360.0
    for i in range(len(_HUES) - 1):
        if _HUES[i] <= h <= _HUES[i + 1]:
            span = _HUES[i + 1] - _HUES[i] or 1.0
            return (i + (h - _HUES[i]) / span) * _STEP % 360.0
    return 0.0


def angle_of(dx, dy):
    """The angle of a point relative to the ring's centre (y grows downward)."""
    return math.degrees(math.atan2(dx, -dy)) % 360.0


def on_band(dx, dy, outer=OUTER, inner=INNER):
    """True if the point lies on the coloured band (not the hole)."""
    d = math.hypot(dx, dy)
    return inner <= d <= outer


def marker_centre(angle, radius=MARKER):
    """(dx, dy) of the marker's centre for an angle."""
    rad = math.radians(angle)
    return radius * math.sin(rad), -radius * math.cos(rad)
