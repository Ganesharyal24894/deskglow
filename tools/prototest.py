#!/usr/bin/env python3
"""Protocol probe: connect via bleak, send power-on then R/G/B in sequence.

Uses the reliable recipe: scan -> stop discovery -> connect (device must be
unbonded so BlueZ resolves services).
"""
import asyncio
from bleak import BleakScanner, BleakClient

from _address import strip_address

ADDRESS = strip_address()
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"


async def scan_for(address, timeout=15.0):
    found = asyncio.get_event_loop().create_future()

    def cb(dev, adv):
        if dev.address.upper() == address.upper() and not found.done():
            found.set_result(dev)

    async with BleakScanner(detection_callback=cb):
        try:
            return await asyncio.wait_for(asyncio.shield(found), timeout)
        except asyncio.TimeoutError:
            return None


async def send(client, data, label):
    print(f"  -> {label}: {data.hex(' ')}")
    await client.write_gatt_char(WRITE_UUID, data, response=False)
    await asyncio.sleep(2.5)


async def main():
    dev = await scan_for(ADDRESS)
    if not dev:
        print("device not found"); return
    await asyncio.sleep(0.5)
    async with BleakClient(dev, timeout=20.0) as c:
        print("connected; running color probe (Triones/Happy-Lighting protocol)")
        await send(c, bytes([0xCC, 0x23, 0x33]), "POWER ON")
        await send(c, bytes([0x56, 0xFF, 0x00, 0x00, 0x00, 0xF0, 0xAA]), "RED")
        await send(c, bytes([0x56, 0x00, 0xFF, 0x00, 0x00, 0xF0, 0xAA]), "GREEN")
        await send(c, bytes([0x56, 0x00, 0x00, 0xFF, 0x00, 0xF0, 0xAA]), "BLUE")
        await send(c, bytes([0x56, 0xFF, 0xFF, 0xFF, 0x00, 0xF0, 0xAA]), "WHITE (RGB)")
        print("done")


asyncio.run(main())
