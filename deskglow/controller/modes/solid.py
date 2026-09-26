"""Solid color mode: ease to a color, then hold it (with keepalive)."""
import asyncio

from .base import Mode
from ...model import color as colormod


class Solid(Mode):
    name = "solid"

    def __init__(self, rgb):
        self.rgb = tuple(int(c) for c in rgb)

    async def run(self, ctx):
        # Ease from whatever is currently lit toward the target over ~0.6s.
        # Starting at black instead would make the strip blink off for the
        # length of the fade every time the colour changes.
        sm = colormod.Smoother(alpha=0.25, start=ctx.last_rgb or (0, 0, 0))
        for _ in range(30):
            await ctx.set(*sm.step(self.rgb))
            await asyncio.sleep(0.02)
        while True:
            await ctx.set(*self.rgb)  # device keepalive re-asserts every ~2s
            await asyncio.sleep(2.0)

    def describe(self):
        return f"solid {self.rgb}"
