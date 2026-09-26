#!/usr/bin/env python3
"""Find the frame that exits the button-induced cycling/effect mode.

Connects once, tries several candidate 'reset to static' sequences, each ending
in a DISTINCT solid color. Watch the strip and note which color it goes SOLID on
(no more blinking). That tells us the reset sequence.
"""
import asyncio
from bleak import BleakScanner, BleakClient

from _address import strip_address

ADDRESS = strip_address()
W = "0000fff3-0000-1000-8000-00805f9b34fb"


def color(r, g, b):
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def effect(i):
    return bytes([0x7E, 0x00, 0x03, i, 0x03, 0x00, 0x00, 0x00, 0xEF])


def speed(s):
    return bytes([0x7E, 0x00, 0x02, s, 0x00, 0x00, 0x00, 0x00, 0xEF])


POWER_ON = bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])
POWER_OFF = bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])


async def scan_for(addr, t=15):
    fut = asyncio.get_event_loop().create_future()
    def cb(d, a):
        if d.address.upper() == addr.upper() and not fut.done():
            fut.set_result(d)
    async with BleakScanner(detection_callback=cb):
        try:
            return await asyncio.wait_for(asyncio.shield(fut), t)
        except asyncio.TimeoutError:
            return None


async def main():
    dev = await scan_for(ADDRESS)
    if not dev:
        print("device not found"); return
    await asyncio.sleep(0.4)
    async with BleakClient(dev, timeout=20) as c:
        async def send(f):
            await c.write_gatt_char(W, f, response=False)
            await asyncio.sleep(0.15)

        # Each attempt: reset-guess, then a distinct SOLID color, hold 6s.
        attempts = [
            ("WHITE  = speed(0) then solid",   [speed(0), color(255, 255, 255)]),
            ("RED    = effect(0x00) then solid", [effect(0x00), color(255, 0, 0)]),
            ("GREEN  = power off/on then solid", [POWER_OFF, POWER_ON, color(0, 255, 0)]),
            ("BLUE   = effect(0xFF) then solid", [effect(0xFF), color(0, 0, 255)]),
            ("YELLOW = effect(0x00)+speed(0) then solid",
             [effect(0x00), speed(0), color(255, 255, 0)]),
        ]
        for label, frames in attempts:
            print(f"\n>>> {label}")
            for f in frames:
                if f is POWER_ON:
                    await asyncio.sleep(0.6)
                await send(f)
            await asyncio.sleep(6.0)
        print("\ndone")


asyncio.run(main())
