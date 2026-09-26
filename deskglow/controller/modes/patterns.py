"""Patterns = the controller's BUILT-IN hardware effects (same set the Lotus
Lantern / Lotus Lamp app exposes), selected with the preset's effect frame.

These run on the strip's own controller (jump / fade / blink through colors), so
they're smooth and need no color streaming over BLE. We just select the effect
and its speed, then re-assert periodically to survive reconnects.
"""
import asyncio

from ...model.presets import get_preset
from .base import Mode

_PRESET = get_preset()
EFFECTS = _PRESET.effects          # name -> effect id, in table order
DEFAULT = _PRESET.default_effect
REASSERT = 15.0  # seconds; re-send effect to recover after any reconnect


class Patterns(Mode):
    name = "pattern"

    def __init__(self, pattern=DEFAULT, speed=50, preset=None):
        effects = preset.effects if preset is not None else EFFECTS
        default = preset.default_effect if preset is not None else DEFAULT
        self.pattern = pattern if pattern in effects else default
        self.effect_id = effects[self.pattern]
        self.speed = max(1, min(100, int(speed)))

    async def run(self, ctx):
        enc = ctx.encoder
        while True:
            # brightness first (ignored by some firmwares while an effect runs,
            # harmless otherwise), then select the effect and its speed.
            # the user's level under the ceiling (firmware brightness, 0-100)
            await ctx.raw(enc.brightness(round(100 * ctx.level())))
            await ctx.raw(enc.effect(self.effect_id))
            await ctx.raw(enc.speed(self.speed))
            await asyncio.sleep(REASSERT)

    def describe(self):
        return f"pattern:{self.pattern}@{self.speed}"


def pattern_names(preset=None):
    return list(preset.effects if preset is not None else EFFECTS)
