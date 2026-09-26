"""Color math: named colors, HSV, colour-temperature, gamma, smoothing."""
import colorsys

RGB = tuple  # (r, g, b) ints 0-255

NAMED = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "warm": (255, 147, 41), "coolwhite": (200, 220, 255),
    "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
    "orange": (255, 90, 0), "purple": (128, 0, 128), "pink": (255, 40, 90),
    "teal": (0, 128, 128), "lavender": (150, 130, 230), "amber": (255, 120, 20),
    "off": (0, 0, 0),
}


def clamp8(v):
    return max(0, min(255, int(round(v))))


def clampf(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def parse(tokens):
    """Parse a color from ['name'] | ['#rrggbb'] | ['r','g','b']."""
    if len(tokens) == 1:
        t = tokens[0].lower()
        if t in NAMED:
            return NAMED[t]
        h = t[1:] if t.startswith("#") else t
        # accept "#ff8800" or bare "ff8800" (zsh eats a leading # as a comment)
        if len(h) == 6 and all(c in "0123456789abcdef" for c in h):
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        raise ValueError(f"unknown color {tokens[0]!r}")
    if len(tokens) == 3:
        return tuple(clamp8(_int_token(x)) for x in tokens)
    raise ValueError(f"cannot parse color from {tokens!r}")


def _int_token(tok):
    """Parse one channel value: decimal by default, or an explicit 0x/0o/0b literal.

    Plain int(tok, 0) would reject zero-padded decimals like "08" (base 0 follows
    Python literal rules), which is exactly what a user or a %02d script types.
    """
    t = str(tok).strip()
    sign = ""
    if t[:1] in "+-":
        sign, t = t[0], t[1:]
    if t[:2].lower() in ("0x", "0o", "0b"):
        return int(sign + t, 0)
    return int(sign + t, 10)


def hsv_to_rgb(h, s, v):
    """h,s,v in 0..1 -> (r,g,b) 0..255."""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clampf(s), clampf(v))
    return (clamp8(r * 255), clamp8(g * 255), clamp8(b * 255))


def rgb_to_hsv(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    return colorsys.rgb_to_hsv(r, g, b)


def scale(rgb, factor):
    """Scale each channel linearly by factor (0..1), clamped to 0-255.

    This is a plain linear scale — apply gamma() separately if you want a
    perceptual curve.
    """
    f = clampf(factor)
    return tuple(clamp8(c * f) for c in rgb)


def lerp(a, b, t):
    """Linear interpolate between two RGB tuples, t in 0..1."""
    t = clampf(t)
    return tuple(clamp8(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gamma(rgb, g=2.2):
    """Apply gamma correction so mid values look right.

    Pure black stays black; callers that want a minimum glow apply their own
    floor (screen mode does).
    """
    return tuple(clamp8(((c / 255.0) ** (1.0 / g)) * 255.0) for c in rgb)


def saturate(rgb, factor):
    """Multiply saturation by factor (>1 more vivid, <1 washed)."""
    h, s, v = rgb_to_hsv(rgb)
    return hsv_to_rgb(h, clampf(s * factor), v)


def kelvin_to_rgb(kelvin):
    """Approximate blackbody colour temperature -> RGB (Tanner Helland)."""
    temp = clampf(kelvin, 1000, 40000) / 100.0
    # red
    if temp <= 66:  # noqa: SIM108 - piecewise form mirrors the published formula
        r = 255
    else:
        r = 329.698727446 * ((temp - 60) ** -0.1332047592)
    # green
    if temp <= 66:
        g = 99.4708025861 * math_log(temp) - 161.1195681661
    else:
        g = 288.1221695283 * ((temp - 60) ** -0.0755148492)
    # blue
    if temp >= 66:
        b = 255
    elif temp <= 19:
        b = 0
    else:
        b = 138.5177312231 * math_log(temp - 10) - 305.0447927307
    return (clamp8(r), clamp8(g), clamp8(b))


def math_log(x):
    import math
    return math.log(max(x, 1e-6))


class Smoother:
    """Exponential moving average toward a target RGB, for smooth transitions."""

    def __init__(self, alpha=0.15, start=(0, 0, 0)):
        self.alpha = alpha
        self.cur = [float(c) for c in start]

    def step(self, target):
        a = self.alpha
        for i in range(3):
            self.cur[i] += (target[i] - self.cur[i]) * a
        return tuple(clamp8(c) for c in self.cur)

    def set(self, rgb):
        self.cur = [float(c) for c in rgb]


def to_hex(rgb):
    """(r, g, b) -> '#RRGGBB' (channels clamped to 0-255)."""
    return "#" + "".join(f"{clamp8(c):02X}" for c in rgb)


def from_hex(text):
    """'#rrggbb' / 'rrggbb' -> (r, g, b), or ValueError."""
    h = str(text).strip().lstrip("#")
    if len(h) != 6 or any(c not in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(f"not a hex colour: {text!r}")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
