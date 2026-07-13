"""Circadian mode: colour temperature + brightness track the time of day.

Cool and bright around midday, warm and dim in the evening/night. Reduces
blue-light exposure late and eye strain over long work sessions. Interpolates
smoothly between keypoints and updates continuously.
"""
import asyncio
import datetime

from .base import Mode
from .. import color as colormod

# (hour, kelvin, brightness_fraction)
KEYPOINTS = [
    (0, 2200, 0.35),
    (6, 2700, 0.50),
    (8, 4000, 0.80),
    (11, 5800, 1.00),
    (14, 6000, 1.00),
    (17, 4600, 0.90),
    (19, 3300, 0.75),
    (21, 2600, 0.55),
    (23, 2300, 0.40),
    (24, 2200, 0.35),  # wrap
]


def _interp(hour):
    for (h0, k0, b0), (h1, k1, b1) in zip(KEYPOINTS, KEYPOINTS[1:]):
        if h0 <= hour < h1:
            t = (hour - h0) / (h1 - h0)
            return (k0 + (k1 - k0) * t, b0 + (b1 - b0) * t)
    return (KEYPOINTS[-1][1], KEYPOINTS[-1][2])


class Circadian(Mode):
    name = "circadian"

    async def run(self, ctx):
        smoother = colormod.Smoother(alpha=0.1)
        while True:
            now = datetime.datetime.now()
            hour = now.hour + now.minute / 60.0
            kelvin, bri = _interp(hour)
            rgb = colormod.scale(colormod.kelvin_to_rgb(kelvin), bri)
            # ease over a few seconds each update tick
            for _ in range(30):
                await ctx.set(*smoother.step(rgb))
                await asyncio.sleep(0.1)
            ctx.log(f"circadian: {hour:.1f}h -> {int(kelvin)}K x{bri:.2f}")
            await asyncio.sleep(27)  # re-evaluate ~every 30s total
