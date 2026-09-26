"""Screen-mode: turn the focused monitor's content into a strip color.

Styles (choose with `deskglow screen <style>`): see controller.modes.sampler.
Capture happens in the ScreenSource (off the event loop); a BLE hiccup or a
failed grab never kills the loop.
"""
import asyncio
import contextlib

from ...model import color as colormod
from .base import Mode
from .geometry import bounding_rect, pick_monitor
from .sampler import STYLES, Sampler

FPS = 15


def _close_quietly(obj):
    """Call obj.close() if it has one; never let cleanup raise."""
    close = getattr(obj, "close", None)
    if close is not None:
        with contextlib.suppress(Exception):
            close()


class Screen(Mode):
    name = "screen"

    async def run(self, ctx):
        source = ctx.services.screen()
        focus = None
        try:
            focus = ctx.services.focus()
            await self._loop(ctx, source, focus)
        finally:
            # Release the display connections this mode opened. Leaking either
            # one per start eventually exhausts the X server's client limit.
            _close_quietly(source)
            _close_quietly(focus)

    async def _loop(self, ctx, source, focus):
        sampler = Sampler(source)
        monitors = await source.monitors()
        smoother = colormod.Smoother(alpha=0.2)
        which = ctx.state.get("screen_monitor", "focus")
        style = ctx.state.get("screen_style", "vivid")
        if style not in STYLES:
            style = "vivid"
        frames = 0
        loop = asyncio.get_event_loop()
        win_start, win_frames = loop.time(), 0
        ctx.log(f"screen-mode: monitors={list(monitors)} target={which} style={style}")
        while True:
            if not monitors:
                # no display yet / no monitors listed — recover instead of crashing
                monitors = await source.monitors()
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
                rect = pick_monitor(monitors, focus.center())
            try:
                raw = await sampler.sample(rect, style)
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
            ctx.telemetry["screen_color"] = tuple(int(c) for c in sm)
            win_frames += 1
            if win_frames >= FPS:        # measured rate, over ~1s windows
                now = loop.time()
                if now > win_start:
                    ctx.telemetry["screen_fps"] = win_frames / (now - win_start)
                win_start, win_frames = now, 0
            if frames % (FPS * 12) == 0:  # ~every 12s
                ctx.log(f"screen alive: {frames} frames, last color {sm}")
            await asyncio.sleep(1.0 / FPS)
