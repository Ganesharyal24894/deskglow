"""Audio-reactive mode: strip brightness follows your PC's audio output level.

An AudioSource captures the default output's monitor (or the mic); this mode
computes a loudness envelope (fast attack, slow decay, like a VU meter) and
maps it to brightness over a slowly drifting hue. A capture that ends is logged
and the mode returns; the source is always stopped.
"""
import asyncio
import contextlib

import numpy as np

from ...model import color as colormod
from .base import Mode

RATE = 22050
CHUNK = 1024          # samples per update (~46ms)
DECAY = 0.86          # envelope decay per chunk (slow release)
GAIN = 6.0            # at the default sensitivity
DEFAULT_SENSITIVITY = 60
FLOOR = 0.06          # never fully dark, so silence still glows a little


def level_of(samples, gain=GAIN):
    """RMS of float samples in -1..1, scaled by `gain` and capped at 1."""
    s = np.asarray(samples, dtype=np.float32)
    rms = float(np.sqrt(np.mean(s * s))) if s.size else 0.0
    return min(1.0, rms * gain)


def gain_for(sensitivity):
    """The level gain for a 1-100 sensitivity (60 = the stock GAIN)."""
    try:
        sens = max(1.0, min(100.0, float(sensitivity)))
    except (TypeError, ValueError):
        sens = DEFAULT_SENSITIVITY
    return GAIN * sens / DEFAULT_SENSITIVITY


class Audio(Mode):
    name = "audio"

    def __init__(self, rgb=None, target=None, source="system"):
        self.base = tuple(int(c) for c in rgb) if rgb else None
        self.target = target
        # "system" = what's playing on the speakers (default output monitor)
        # "mic"    = the microphone / default input
        self.source = source if source in ("system", "mic") else "system"

    async def run(self, ctx):
        src = ctx.services.audio()
        try:
            desc = await src.start(self.source, self.target, RATE, CHUNK)
            ctx.log(f"audio: source={self.source} capturing via {desc}")
            await self._loop(ctx, src)
        finally:
            with contextlib.suppress(Exception):
                await src.stop()

    async def _loop(self, ctx, src):
        env = 0.0
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        while True:
            samples = await src.read()
            if samples is None:
                ctx.log("audio: capture stream ended")
                return
            # read every block, so the sensitivity slider applies at once
            gain = gain_for(ctx.state.get("audio_sensitivity", DEFAULT_SENSITIVITY))
            env = max(level_of(samples, gain), env * DECAY)   # fast attack, slow decay
            ctx.telemetry["audio_level"] = env
            bri = FLOOR + (1.0 - FLOOR) * env
            if self.base is not None:
                col = self.base
            else:
                hue = ((loop.time() - t0) * 0.03) % 1.0  # slow drift
                col = colormod.hsv_to_rgb(hue, 0.85, 1.0)
            await ctx.set(*colormod.scale(col, bri))

    def describe(self):
        return f"audio-reactive ({self.source})"
