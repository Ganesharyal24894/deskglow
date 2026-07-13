"""Solid color mode: ease to a color, then hold it (with keepalive)."""
import asyncio

from .base import Mode
from .. import color as colormod


class Solid(Mode):
    name = "solid"

    def __init__(self, rgb):
        self.rgb = tuple(int(c) for c in rgb)

    async def run(self, ctx):
        # smooth fade-in from current toward target over ~0.6s
        sm = colormod.Smoother(alpha=0.25)
        for _ in range(30):
            await ctx.set(*sm.step(self.rgb))
            await asyncio.sleep(0.02)
        while True:
            await ctx.set(*self.rgb)  # device keepalive re-asserts every ~2s
            await asyncio.sleep(2.0)

    def describe(self):
        return f"solid {self.rgb}"
