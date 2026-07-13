#!/usr/bin/env python3
"""Fast protocol probe. Connect once, send hex command(s) passed on the CLI.

Usage:
    python probe.py "7E 00 05 03 FF 00 00 00 EF"          # one command
    python probe.py "cmd1..." "cmd2..." --delay 2.5        # several, spaced out
    python probe.py --listen 8  "7E ..."                   # also print notifications

Each arg is a whitespace-separated hex byte string (0x prefixes optional).
"""
import argparse
import asyncio
from bleak import BleakScanner, BleakClient

ADDRESS = "BE:69:4C:0F:1E:2F"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"


def parse_hex(s):
    return bytes(int(tok, 16) for tok in s.replace("0x", "").replace(",", " ").split())


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


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("commands", nargs="+")
    ap.add_argument("--delay", type=float, default=2.5)
    ap.add_argument("--listen", type=float, default=0.0,
                    help="seconds to listen for notifications after sending")
    ap.add_argument("--response", action="store_true",
                    help="use write-with-response")
    args = ap.parse_args()

    dev = await scan_for(ADDRESS)
    if not dev:
        print("device not found"); return
    await asyncio.sleep(0.4)
    async with BleakClient(dev, timeout=20.0) as c:
        print("connected")

        if args.listen:
            def on_notify(_, data):
                print(f"  <== NOTIFY: {data.hex(' ')}")
            try:
                await c.start_notify(NOTIFY_UUID, on_notify)
                print("listening on fff4")
            except Exception as e:
                print(f"  (notify subscribe failed: {e})")

        for cmd in args.commands:
            data = parse_hex(cmd)
            print(f"  ==> {data.hex(' ')}")
            await c.write_gatt_char(WRITE_UUID, data, response=args.response)
            await asyncio.sleep(args.delay)

        if args.listen:
            await asyncio.sleep(args.listen)
        print("done")


asyncio.run(main())
