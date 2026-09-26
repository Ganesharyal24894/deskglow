#!/usr/bin/env python3
"""Decisive test: force STATIC blue with reliable (with-response) writes, then
ramp brightness. Tells us effect-mode vs brownout.

  - stays solid blue all the way  -> it was an effect; reliable static write fixes it
  - blinking returns at some level -> power/brownout at that current
"""
import asyncio
from bleak import BleakScanner, BleakClient

from _address import strip_address

ADDRESS = strip_address()
W = "0000fff3-0000-1000-8000-00805f9b34fb"

def color(r, g, b): return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])
def bright(p):      return bytes([0x7E, 0x00, 0x01, p, 0x00, 0x00, 0x00, 0x00, 0xEF])
POWER_ON = bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])


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
        async def send(f, resp=True):
            await c.write_gatt_char(W, f, response=resp)
            await asyncio.sleep(0.2)

        print(">>> forcing STATIC blue with reliable (with-response) writes")
        await send(POWER_ON)
        await send(color(0, 0, 255))
        await send(color(0, 0, 255))   # twice, to be sure it registers
        print("    (should be solid blue now — is it?)")
        await asyncio.sleep(5)
        for p in [30, 40, 50, 60, 70, 85, 100]:
            await send(bright(p))
            await send(color(0, 0, 255))   # re-assert color after brightness
            print(f">>> brightness {p}%  (watch for blinking)")
            await asyncio.sleep(6)
        print("done — leaving it at 100%")


asyncio.run(main())
