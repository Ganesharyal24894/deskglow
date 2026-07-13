"""Calm mode: eye-pleasing colors drift one into the next, each breathing gently.

Palette is deliberately low/mid saturation (no harsh primaries) and the colors
cross-fade slowly with a slow brightness "breathing" envelope on top.
"""
import asyncio
import math

from .base import Mode
from .. import color as colormod

# soft, desaturated, low-eye-strain colors
PALETTE = [
    (90, 140, 170),    # dusty blue
    (120, 150, 140),   # sage
    (150, 130, 200),   # soft lavender
    (170, 130, 150),   # dusty rose
    (110, 160, 165),   # muted teal
    (160, 150, 120),   # warm sand
    (100, 130, 180),   # periwinkle
]

FADE = 40.0        # seconds to drift from one color to the next
BREATH_PERIOD = 11.0  # seconds per breath
BREATH_MIN = 0.45  # dimmest point of the breath (fraction)
FPS = 30


class Calm(Mode):
    name = "calm"

    async def run(self, ctx):
        loop = asyncio.get_event_loop()
        i = 0
        t0 = loop.time()
        while True:
            a = PALETTE[i % len(PALETTE)]
            b = PALETTE[(i + 1) % len(PALETTE)]
            seg_start = loop.time()
            while True:
                now = loop.time()
                frac = (now - seg_start) / FADE
                if frac >= 1.0:
                    break
                base = colormod.lerp(a, b, frac)
                breath = BREATH_MIN + (1 - BREATH_MIN) * (
                    0.5 + 0.5 * math.sin(2 * math.pi * (now - t0) / BREATH_PERIOD))
                await ctx.set(*colormod.scale(base, breath))
                await asyncio.sleep(1.0 / FPS)
            i += 1
