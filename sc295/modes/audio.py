"""Audio-reactive mode: strip brightness follows your PC's audio output level.

Captures the default sink's monitor via PipeWire (`pw-record`), computes a
loudness envelope (fast attack, slow decay, like a VU meter), and maps it to
brightness over a slowly drifting hue. Falls back gracefully if capture fails.
"""
import asyncio
import json
import math
import subprocess

import numpy as np

from .base import Mode
from .. import color as colormod

RATE = 22050
CHUNK = 1024          # samples per update (~46ms)
DECAY = 0.86          # envelope decay per chunk (slow release)
GAIN = 6.0
FLOOR = 0.06          # never fully dark, so silence still glows a little


def _default_sink_name():
    """Best-effort: find an Audio/Sink node name to record its monitor from."""
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True,
                             timeout=5).stdout
        data = json.loads(out)
        for obj in data:
            props = (obj.get("info") or {}).get("props") or {}
            if props.get("media.class") == "Audio/Sink":
                return props.get("node.name")
    except Exception:
        return None
    return None


class Audio(Mode):
    name = "audio"

    def __init__(self, rgb=None, target=None, source="system"):
        self.base = tuple(int(c) for c in rgb) if rgb else None
        self.target = target
        # "system" = what's playing on the speakers (default sink monitor)
        # "mic"    = the microphone / default input
        self.source = source if source in ("system", "mic") else "system"

    async def run(self, ctx):
        if self.target:
            target = self.target
        elif self.source == "mic":
            target = None  # pw-record with no target captures the default input
        else:
            target = _default_sink_name()  # capture the speaker output's monitor
        cmd = ["pw-record", "--rate", str(RATE), "--channels", "1",
               "--format", "s16"]
        if target:
            cmd += ["--target", target]
        cmd += ["-"]
        ctx.log(f"audio: source={self.source} capturing via {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        env = 0.0
        hue = 0.0
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        try:
            while True:
                try:
                    raw = await proc.stdout.readexactly(CHUNK * 2)
                except asyncio.IncompleteReadError:
                    ctx.log("audio: capture stream ended")
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(samples * samples))) / 32768.0
                level = min(1.0, rms * GAIN)
                env = max(level, env * DECAY)     # fast attack, slow decay
                bri = FLOOR + (1.0 - FLOOR) * env
                if self.base is not None:
                    col = self.base
                else:
                    hue = ((loop.time() - t0) * 0.03) % 1.0  # slow drift
                    col = colormod.hsv_to_rgb(hue, 0.85, 1.0)
                await ctx.set(*colormod.scale(col, bri))
        finally:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except Exception:
                pass

    def describe(self):
        return f"audio-reactive ({self.source})"
