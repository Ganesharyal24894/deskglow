"""Pomodoro / focus-timer mode: the strip's color tells you the phase.

  focus  -> calm cyan, steady
  last minute of focus -> gentle pulse to warn the break is near
  break  -> warm green, steady; a short triple-pulse marks each transition
After the configured rounds it settles on a soft "done" color.
"""
import asyncio
import math

from .base import Mode
from .. import color as colormod

FOCUS_COLOR = (40, 150, 190)   # calm cyan
BREAK_COLOR = (70, 180, 90)    # soft green
DONE_COLOR = (150, 130, 200)   # lavender
FPS = 30


class Pomodoro(Mode):
    name = "pomodoro"

    def __init__(self, work=25, brk=5, rounds=4):
        self.work = float(work)
        self.brk = float(brk)
        self.rounds = int(rounds)

    async def _pulse(self, ctx, color, times=3, period=0.6):
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        while loop.time() - t0 < times * period:
            phase = (loop.time() - t0) / period
            b = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * phase))
            await ctx.set(*colormod.scale(color, b))
            await asyncio.sleep(1.0 / FPS)

    async def _phase(self, ctx, color, minutes, warn=True):
        loop = asyncio.get_event_loop()
        end = loop.time() + minutes * 60.0
        while True:
            remaining = end - loop.time()
            if remaining <= 0:
                break
            if warn and remaining <= 60:
                # gentle breathing during the final minute
                b = 0.5 + 0.5 * (0.5 + 0.5 * math.sin(loop.time() * 2.5))
                await ctx.set(*colormod.scale(color, b))
            else:
                await ctx.set(*color)
            await asyncio.sleep(1.0 / FPS)

    async def run(self, ctx):
        for r in range(1, self.rounds + 1):
            ctx.log(f"pomodoro: focus round {r}/{self.rounds} ({self.work:g}m)")
            await self._pulse(ctx, FOCUS_COLOR, times=2)
            await self._phase(ctx, FOCUS_COLOR, self.work)
            if r < self.rounds:
                ctx.log(f"pomodoro: break ({self.brk:g}m)")
                await self._pulse(ctx, BREAK_COLOR, times=3)
                await self._phase(ctx, BREAK_COLOR, self.brk, warn=True)
        ctx.log("pomodoro: all rounds done")
        while True:
            await ctx.set(*DONE_COLOR)
            await asyncio.sleep(2.0)

    def describe(self):
        return f"pomodoro {self.work:g}/{self.brk:g}x{self.rounds}"
