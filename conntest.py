#!/usr/bin/env python3
"""Minimal bleak connection test for the MELK controller."""
import asyncio
from bleak import BleakClient

ADDRESS = "BE:69:4C:0F:1E:2F"


async def main():
    for attempt in range(1, 4):
        try:
            print(f"connect attempt {attempt} ...")
            async with BleakClient(ADDRESS, timeout=25.0) as c:
                print("CONNECTED:", c.is_connected)
                for s in c.services:
                    for ch in s.characteristics:
                        print(f"  {ch.uuid}  props={ch.properties}")
                return
        except Exception as e:
            print(f"  fail: {type(e).__name__}: {e}")
            await asyncio.sleep(1)


asyncio.run(main())
