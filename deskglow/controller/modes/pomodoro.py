"""Pomodoro / focus-timer mode: the strip's color tells you the phase.

  focus  -> calm cyan, steady
  break  -> soft green, steady; a short pulse burst marks each transition
  the last minute of either phase breathes gently, to warn the switch is near
After the configured rounds it settles on a soft "done" color.

The mode publishes its phase and remaining time in ctx.telemetry["focus"] and
honours ctx.controls["paused"]: while paused the clock stands still.
"""
import asyncio
import math

from .base import Mode
from ...model import color as colormod

FOCUS_COLOR = (40, 160, 200)   # calm cyan (#28A0C8)
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

    def _publish(self, ctx, phase, remaining, total, rnd):
        ctx.telemetry["focus"] = {
            "phase": phase, "remaining": max(0.0, remaining), "total": total,
            "round": rnd, "rounds": self.rounds, "paused": bool(ctx.controls.get("paused"))}

    async def _phase(self, ctx, color, minutes, warn=True, phase="focus", rnd=1):
        loop = asyncio.get_event_loop()
        total = minutes * 60.0
        last = loop.time()
        end = last + total
        while True:
            now = loop.time()
            paused = bool(ctx.controls.get("paused"))
            if paused:
                end += now - last        # time spent paused doesn't count
            last = now
            remaining = end - now
            self._publish(ctx, phase, remaining, total, rnd)
            if remaining <= 0:
                break
            if warn and remaining <= 60 and not paused:
                # gentle breathing during the final minute
                b = 0.5 + 0.5 * (0.5 + 0.5 * math.sin(loop.time() * 2.5))
                await ctx.set(*colormod.scale(color, b))
            else:
                await ctx.set(*color)
            await asyncio.sleep(1.0 / FPS)

    async def run(self, ctx):
        for r in range(1, self.rounds + 1):
            ctx.log(f"pomodoro: focus round {r}/{self.rounds} ({self.work:g}m)")
            self._publish(ctx, "focus", self.work * 60.0, self.work * 60.0, r)
            await self._pulse(ctx, FOCUS_COLOR, times=2)
            await self._phase(ctx, FOCUS_COLOR, self.work, phase="focus", rnd=r)
            if r < self.rounds:
                ctx.log(f"pomodoro: break ({self.brk:g}m)")
                self._publish(ctx, "break", self.brk * 60.0, self.brk * 60.0, r)
                await self._pulse(ctx, BREAK_COLOR, times=3)
                await self._phase(ctx, BREAK_COLOR, self.brk, warn=True, phase="break", rnd=r)
        ctx.log("pomodoro: all rounds done")
        self._publish(ctx, "done", 0.0, 0.0, self.rounds)
        while True:
            await ctx.set(*DONE_COLOR)
            await asyncio.sleep(2.0)

    def describe(self):
        return f"pomodoro {self.work:g}/{self.brk:g}x{self.rounds}"
