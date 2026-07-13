#!/usr/bin/env python3
"""Connection test using bleak-retry-connector (handles BlueZ quirks)."""
import asyncio
from bleak import BleakScanner
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

ADDRESS = "BE:69:4C:0F:1E:2F"


async def main():
    print("finding device...")
    dev = await BleakScanner.find_device_by_address(ADDRESS, timeout=15.0)
    if not dev:
        print("not found in scan; aborting")
        return
    print(f"found {dev.name!r}; establishing connection...")
    client = await establish_connection(
        BleakClientWithServiceCache, dev, dev.name or ADDRESS, max_attempts=5
    )
    print("CONNECTED:", client.is_connected)
    for s in client.services:
        for ch in s.characteristics:
            print(f"  {ch.uuid}  props={ch.properties}")
    await client.disconnect()
    print("disconnected cleanly")


asyncio.run(main())
