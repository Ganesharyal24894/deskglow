#!/usr/bin/env python3
"""Discover the LED strip: scan for it, connect, and dump its GATT table.

This tells us which characteristic to write commands to. Run this first.
"""
import asyncio
import sys

from bleak import BleakScanner, BleakClient

from _address import strip_address

ADDRESS = strip_address()


def props(char):
    return ",".join(char.properties)


async def find_device():
    print(f"Scanning for {ADDRESS} ...")
    dev = await BleakScanner.find_device_by_address(ADDRESS, timeout=15.0)
    if dev:
        print(f"  found: {dev.name!r} @ {dev.address}")
    return dev


async def enumerate_gatt(device):
    target = device if device is not None else ADDRESS
    last_err = None
    for attempt in range(1, 5):
        try:
            print(f"\nConnecting (attempt {attempt}/4)...")
            async with BleakClient(target, timeout=20.0) as client:
                print(f"Connected: {client.is_connected}\n")
                for service in client.services:
                    print(f"[Service] {service.uuid}  ({service.description})")
                    for char in service.characteristics:
                        print(f"    [Char] {char.uuid}  props=({props(char)})  handle={char.handle}")
                        if "read" in char.properties:
                            try:
                                val = await client.read_gatt_char(char)
                                print(f"           value: {val.hex()}  {val!r}")
                            except Exception as e:
                                print(f"           (read failed: {e})")
                        for desc in char.descriptors:
                            print(f"        [Desc] {desc.uuid}  handle={desc.handle}")
                print("\nWrite-capable characteristics (candidates for sending commands):")
                for service in client.services:
                    for char in service.characteristics:
                        if "write" in char.properties or "write-without-response" in char.properties:
                            print(f"    {char.uuid}  props=({props(char)})")
                return True
        except Exception as e:
            last_err = e
            print(f"  attempt {attempt} failed: {type(e).__name__}: {e}")
            await asyncio.sleep(2.0)
    print(f"\nAll attempts failed. Last error: {last_err}", file=sys.stderr)
    return False


async def main():
    dev = await find_device()
    if not dev:
        print("!! Not found in scan (phone app may be holding the connection). "
              "Trying by address anyway...")
    await enumerate_gatt(dev)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
