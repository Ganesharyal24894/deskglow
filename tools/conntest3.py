#!/usr/bin/env python3
"""Robust connect: scan until found, STOP discovery, then connect."""
import asyncio
from bleak import BleakScanner, BleakClient

from _address import strip_address

ADDRESS = strip_address()


async def scan_for(address, timeout=15.0):
    """Scan and return the BLEDevice, stopping discovery on exit."""
    found = asyncio.get_event_loop().create_future()

    def cb(dev, adv):
        if dev.address.upper() == address.upper() and not found.done():
            found.set_result(dev)

    async with BleakScanner(detection_callback=cb):
        try:
            return await asyncio.wait_for(asyncio.shield(found), timeout)
        except asyncio.TimeoutError:
            return None
    # leaving the context manager stops discovery


async def main():
    print("scanning (discovery will be stopped before connect)...")
    dev = await scan_for(ADDRESS)
    if not dev:
        print("device not found in scan")
        return
    print(f"found {dev.name!r}; discovery stopped; connecting...")
    await asyncio.sleep(0.5)  # let BlueZ settle after stopping discovery
    for attempt in range(1, 4):
        try:
            async with BleakClient(dev, timeout=20.0) as c:
                print("CONNECTED:", c.is_connected)
                for s in c.services:
                    for ch in s.characteristics:
                        print(f"  {ch.uuid}  props={ch.properties}")
                return
        except Exception as e:
            print(f"  attempt {attempt} fail: {type(e).__name__}: {e}")
            await asyncio.sleep(1.5)


asyncio.run(main())
