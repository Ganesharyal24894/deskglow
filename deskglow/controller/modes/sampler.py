"""Reduce a grabbed screen image to one RGB colour, by style.

Styles:
  average  - mean color of the whole image (calm, muted bias light)
  vivid    - saturation-weighted average (colorful, lively)
  dominant - the dominant hue rendered punchy and clean
  edge     - average of the border only (ambilight-style)
All styles operate on a downsampled float copy for speed.
"""
import colorsys

import numpy as np

from ...model.settings import SCREEN_STYLES

STYLES = SCREEN_STYLES
SAMPLE_WIDTH = 220   # ~220px wide sample grid


def downsample(img):
    """HxWx3 uint8 array-like -> a ~SAMPLE_WIDTH-wide float32 copy."""
    arr = np.asarray(img)
    step = max(1, arr.shape[1] // SAMPLE_WIDTH)
    return arr[::step, ::step].astype(np.float32)


def reduce(arr, style="average"):
    """One (r, g, b) float tuple in 0..255 for an HxWx3 float image."""
    if style == "edge":
        return _edge(arr)
    flat = arr.reshape(-1, 3)
    if style == "vivid":
        return _vivid(flat)
    if style == "dominant":
        return _dominant(flat)
    return _tuple(flat.mean(axis=0))  # average (and any unknown style)


class Sampler:
    """Grabs a rect from a ScreenSource and reduces it by the chosen style."""

    def __init__(self, source):
        self.source = source

    async def sample(self, rect, style="average"):
        img = await self.source.grab(rect)
        return reduce(downsample(img), style)


def _edge(arr):
    h, w, _ = arr.shape
    b = max(2, h // 12)
    bands = [arr[:b], arr[-b:], arr[:, :b], arr[:, -b:]]
    border = np.concatenate([x.reshape(-1, 3) for x in bands])
    return _tuple(border.mean(axis=0))


def _hsv_parts(flat):
    mx = flat.max(axis=1)
    mn = flat.min(axis=1)
    v = mx / 255.0
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return s, v


def _vivid(flat):
    """Saturation-weighted average: grey pixels contribute ~nothing (s^3),
    so even a small colorful region drives the result. Robust when the
    vivid area is only a few percent of the screen."""
    s, v = _hsv_parts(flat)
    weight = (s ** 3) * v
    total = weight.sum()
    if weight.max() < 0.06 or total < 1e-6:   # basically greyscale
        return _tuple(flat.mean(axis=0))
    col = (flat * weight[:, None]).sum(axis=0) / total
    return _boost_saturation(col, 1.3)


def _dominant(flat):
    """Most common hue (quantized), weighted by saturation*brightness,
    rendered at high saturation. More stable/punchier than 'vivid'."""
    s, v = _hsv_parts(flat)
    weight = (s ** 1.5) * v
    if weight.max() < 0.06:
        return _tuple(flat.mean(axis=0))
    # quantize each channel to 6 levels -> 216 buckets, weighted histogram
    q = np.clip((flat / 256.0 * 6).astype(np.int32), 0, 5)
    keys = q[:, 0] * 36 + q[:, 1] * 6 + q[:, 2]
    totals = np.bincount(keys, weights=weight, minlength=216)
    best = int(totals.argmax())
    mask = keys == best
    col = flat[mask].mean(axis=0)
    return _boost_saturation(col, 1.5)


def _tuple(a):
    return (float(a[0]), float(a[1]), float(a[2]))


def _boost_saturation(col, factor):
    r, g, b = (float(c) / 255.0 for c in col)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * factor), v)
    return (r * 255.0, g * 255.0, b * 255.0)
