"""Screen-mode: turn the focused monitor's content into a strip color.

Styles (choose with `sc295 screen <style>`):
  average  - mean color of the whole screen (calm, muted bias light)
  vivid    - average of the most saturated pixels (colorful, lively)   [default]
  dominant - the dominant screen hue rendered punchy and clean
  edge     - average of the screen border only (ambilight-style)

Capture runs in a worker thread; a BLE hiccup never kills the loop.
"""
import asyncio
import concurrent.futures

from .base import Mode
from .. import color as colormod
from ..screen_util import (ActiveWindow, Sampler, STYLES, get_monitors,
                           pick_monitor, bounding_rect)

FPS = 15


class Screen(Mode):
    name = "screen"

    async def run(self, ctx):
        loop = asyncio.get_event_loop()
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        sampler = Sampler()
        aw = ActiveWindow()
        monitors = await loop.run_in_executor(pool, get_monitors)
        smoother = colormod.Smoother(alpha=0.2)
        which = ctx.state.get("screen_monitor", "focus")
        style = ctx.state.get("screen_style", "vivid")
        if style not in STYLES:
            style = "vivid"
        frames = 0
        ctx.log(f"screen-mode: monitors={list(monitors)} target={which} style={style}")
        try:
            while True:
                if not monitors:
                    # no X display yet / xrandr empty — recover instead of crashing
                    monitors = await loop.run_in_executor(pool, get_monitors)
                    if not monitors:
                        ctx.log("screen: no monitors/display available; retrying")
                        await asyncio.sleep(3)
                        continue
                    ctx.log(f"screen: monitors now {list(monitors)}")
                if which == "both":
                    rect = bounding_rect(monitors)
                elif which in monitors:
                    rect = monitors[which]
                else:  # focus
                    rect = pick_monitor(monitors, aw.center())
                try:
                    raw = await loop.run_in_executor(pool, sampler.sample, rect, style)
                except Exception as e:
                    ctx.log(f"screen capture error: {e}")
                    await asyncio.sleep(0.5)
                    continue
                col = colormod.gamma(tuple(int(c) for c in raw), 1.6)
                if any(raw):
                    col = tuple(max(c, 4) for c in col)  # faint glow, never fully off
                sm = smoother.step(col)
                # Always call set(): the device layer de-dups identical colors
                # but re-asserts every ~2s as a keepalive, which keeps the BLE
                # link from timing out when the screen color is static.
                try:
                    await ctx.set(*sm)
                except Exception as e:
                    ctx.log(f"screen set error (continuing): {type(e).__name__}")
                frames += 1
                if frames % (FPS * 12) == 0:  # ~every 12s
                    ctx.log(f"screen alive: {frames} frames, last color {sm}")
                await asyncio.sleep(1.0 / FPS)
        finally:
            pool.shutdown(wait=False)
