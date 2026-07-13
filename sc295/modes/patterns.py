"""Patterns = the controller's BUILT-IN hardware effects (same set the Lotus
Lantern / Lotus Lamp app exposes), triggered with the 0x03 effect command.

These run on the strip's own controller (jump / fade / blink through colors), so
they're smooth and need no color streaming over BLE. We just select the effect
and its speed, then re-assert periodically to survive reconnects.
"""
import asyncio

from .base import Mode
from .. import protocol

# name -> effect id (from the ELK/MELK 0x87-0x9C built-in effect table)
EFFECTS = {
    "jump-rgb": 0x87,          # jump red/green/blue
    "jump-colors": 0x88,       # jump through 7 colors
    "fade-rgb": 0x89,          # smooth crossfade red/green/blue
    "fade-colors": 0x8A,       # smooth crossfade through 7 colors
    "fade-red": 0x8B,
    "fade-green": 0x8C,
    "fade-blue": 0x8D,
    "fade-yellow": 0x8E,
    "fade-cyan": 0x8F,
    "fade-magenta": 0x90,
    "fade-white": 0x91,
    "fade-red-green": 0x92,
    "fade-red-blue": 0x93,
    "fade-green-blue": 0x94,
    "blink-colors": 0x95,      # strobe through 7 colors
    "blink-red": 0x96,
    "blink-green": 0x97,
    "blink-blue": 0x98,
    "blink-yellow": 0x99,
    "blink-cyan": 0x9A,
    "blink-magenta": 0x9B,
    "blink-white": 0x9C,
}

DEFAULT = "fade-colors"
REASSERT = 15.0  # seconds; re-send effect to recover after any reconnect


class Patterns(Mode):
    name = "pattern"

    def __init__(self, pattern=DEFAULT, speed=50):
        self.pattern = pattern if pattern in EFFECTS else DEFAULT
        self.effect_id = EFFECTS[self.pattern]
        self.speed = max(1, min(100, int(speed)))

    async def run(self, ctx):
        while True:
            # brightness first (ignored by some firmwares while an effect runs,
            # harmless otherwise), then select the effect and its speed.
            bri = ctx.state.get("max_brightness", 100)
            await ctx.raw(protocol.brightness(bri))
            await ctx.raw(protocol.effect(self.effect_id))
            await ctx.raw(protocol.speed(self.speed))
            await asyncio.sleep(REASSERT)

    def describe(self):
        return f"pattern:{self.pattern}@{self.speed}"


def pattern_names():
    return list(EFFECTS)
