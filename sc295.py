#!/usr/bin/env python3
"""sc295 — minimal CLI to control the MELK-OA10 / SC295 BLE LED strip.

Protocol: ELK-BLEDOM (9-byte frames, 0x7E .. 0xEF) written to characteristic fff3.

Examples:
    python sc295.py on
    python sc295.py color red
    python sc295.py color 255 128 0
    python sc295.py brightness 50
    python sc295.py effect 0x87 --speed 40
    python sc295.py raw 7E 00 05 03 FF 00 00 00 EF
    python sc295.py repl            # hold one connection, type commands live
    python sc295.py monitor 15      # subscribe to notifications for 15s
    python sc295.py fix-connection  # drop a stale BlueZ bond if connects hang
"""
import argparse
import asyncio
import subprocess
import sys

from bleak import BleakScanner, BleakClient

ADDRESS = "BE:69:4C:0F:1E:2F"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# Protocol encoding (ELK-BLEDOM)
# ---------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def cmd_power(on):
    # on:  7E 00 04 F0 00 01 FF 00 EF
    # off: 7E 00 04 00 00 00 FF 00 EF
    if on:
        return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])
    return bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])


def cmd_color(r, g, b):
    r, g, b = (_clamp(x, 0, 255) for x in (r, g, b))
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def cmd_brightness(pct):
    # 0-100 percent
    p = _clamp(pct, 0, 100)
    return bytes([0x7E, 0x00, 0x01, p, 0x00, 0x00, 0x00, 0x00, 0xEF])


def cmd_effect(effect_id):
    e = _clamp(effect_id, 0, 255)
    return bytes([0x7E, 0x00, 0x03, e, 0x03, 0x00, 0x00, 0x00, 0xEF])


def cmd_speed(pct):
    p = _clamp(pct, 0, 100)
    return bytes([0x7E, 0x00, 0x02, p, 0x00, 0x00, 0x00, 0x00, 0xEF])


COLORS = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255), "warm": (255, 147, 41), "yellow": (255, 255, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255), "orange": (255, 90, 0),
    "purple": (128, 0, 128), "pink": (255, 40, 90), "off": (0, 0, 0),
}


def resolve_color(tokens):
    """Accept a color name or three 0-255 ints (dec or 0x hex)."""
    if len(tokens) == 1 and tokens[0].lower() in COLORS:
        return COLORS[tokens[0].lower()]
    if len(tokens) == 1 and tokens[0].startswith("#") and len(tokens[0]) == 7:
        h = tokens[0][1:]
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if len(tokens) == 3:
        return tuple(int(t, 0) for t in tokens)
    raise SystemExit(f"cannot parse color from {tokens!r}; "
                     f"use a name ({', '.join(COLORS)}), #rrggbb, or 'R G B'")


def parse_hex(tokens):
    return bytes(int(t, 16) for t in tokens)

# ---------------------------------------------------------------------------
# Connection layer
# ---------------------------------------------------------------------------

async def _scan_for(address, timeout):
    found = asyncio.get_event_loop().create_future()

    def cb(dev, _adv):
        if dev.address.upper() == address.upper() and not found.done():
            found.set_result(dev)

    async with BleakScanner(detection_callback=cb):
        try:
            return await asyncio.wait_for(asyncio.shield(found), timeout)
        except asyncio.TimeoutError:
            return None
    # scanner context exit stops discovery, which BlueZ needs before connecting


def _drop_bond():
    """Remove a stale BlueZ bond (the cause of ServicesResolved hangs)."""
    try:
        subprocess.run(["bluetoothctl", "remove", ADDRESS],
                       capture_output=True, timeout=10)
    except Exception:
        pass


async def connect(scan_timeout=15.0, auto_fix=True):
    """Return a connected BleakClient using the reliable recipe."""
    dev = await _scan_for(ADDRESS, scan_timeout)
    if not dev:
        raise SystemExit(f"device {ADDRESS} not found (powered on? in range? "
                         f"still connected to the phone app?)")
    await asyncio.sleep(0.4)
    client = BleakClient(dev, timeout=20.0)
    try:
        await client.connect()
        return client
    except Exception as e:
        if not auto_fix:
            raise
        # Most likely a stale bond blocking service resolution — drop it & retry.
        print(f"connect failed ({type(e).__name__}); dropping stale bond and retrying...",
              file=sys.stderr)
        _drop_bond()
        dev = await _scan_for(ADDRESS, scan_timeout)
        if not dev:
            raise SystemExit("device vanished after bond reset")
        await asyncio.sleep(0.4)
        client = BleakClient(dev, timeout=20.0)
        await client.connect()
        return client


async def send(client, data):
    await client.write_gatt_char(WRITE_UUID, data, response=False)

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def run_once(frames, hold=0.0):
    """Connect, send one or more frames, disconnect."""
    client = await connect()
    try:
        for f in frames:
            print(f"  ==> {f.hex(' ')}")
            await send(client, f)
            await asyncio.sleep(0.05)
        if hold:
            await asyncio.sleep(hold)
    finally:
        await client.disconnect()


async def monitor(seconds):
    client = await connect()
    try:
        def on_notify(_, data):
            print(f"  <== {data.hex(' ')}")
        await client.start_notify(NOTIFY_UUID, on_notify)
        # Ask the device for its state (some firmwares reply on fff4).
        await send(client, bytes([0x7E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF]))
        print(f"listening {seconds}s on fff4 (Ctrl-C to stop)...")
        await asyncio.sleep(seconds)
    finally:
        await client.disconnect()


async def sweep(color, levels, hold):
    """Diagnostic: hold `color`, step brightness through `levels`, announcing each.

    Two signals to watch for:
      1. Visual: the brightness where the flicker STOPS. If it stops when dimmed,
         the cause is current/power (lower PWM duty -> lower average current ->
         the supply stops browning out).
      2. BLE stability: this logs every disconnect. If the link drops only at high
         brightness, the strip's controller (incl. its BLE radio) is browning out.
    """
    drops = {}  # level -> number of disconnects seen during its hold

    async def ensure(client, current_level):
        """Return a connected client, reconnecting if the link dropped."""
        if client is not None and client.is_connected:
            return client
        if client is not None:
            drops[current_level] = drops.get(current_level, 0) + 1
            print(f"    !! BLE link dropped at {current_level}% brightness "
                  f"-> reconnecting")
        return await connect()

    client = await connect()
    try:
        print(f"holding color {color}; watch where flicker STOPS.")
        await send(client, cmd_power(True))
        await send(client, cmd_color(*color))
        for lvl in levels:
            client = await ensure(client, lvl)
            try:
                await send(client, cmd_brightness(lvl))
                # keep the color asserted too, in case a reconnect reset it
                await send(client, cmd_color(*color))
            except Exception:
                client = await ensure(client, lvl)
                await send(client, cmd_brightness(lvl))
            print(f"  brightness = {lvl:3d}%   (hold {hold}s)")
            # poll connection during the hold so we notice drops promptly
            waited = 0.0
            while waited < hold:
                await asyncio.sleep(0.5)
                waited += 0.5
                if not client.is_connected:
                    client = await ensure(client, lvl)
                    await send(client, cmd_brightness(lvl))
                    await send(client, cmd_color(*color))
        print("\nsweep done.")
        if drops:
            print("BLE drops by brightness level:")
            for lvl in sorted(drops, reverse=True):
                print(f"    {lvl:3d}%: {drops[lvl]} drop(s)")
        else:
            print("No BLE drops observed during the sweep.")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def soak(color, seconds, reassert):
    """Hold `color` at FULL brightness for `seconds`, watching for the flicker.

    Sends ONE clean set of commands (no app-style chatter), then just holds so
    we can tell whether the strip flickers on its own vs. only when an app is
    actively driving it. Logs any BLE drops with elapsed timestamps.
    """
    client = await connect()
    elapsed = 0.0
    drops = 0
    try:
        await send(client, cmd_power(True))
        await send(client, cmd_brightness(100))
        await send(client, cmd_color(*color))
        print(f"holding {color} at 100% for {seconds:.0f}s. Watch for any flicker "
              f"and note the elapsed time when it happens.")
        while elapsed < seconds:
            await asyncio.sleep(1.0)
            elapsed += 1.0
            if not client.is_connected:
                drops += 1
                print(f"  [{elapsed:5.0f}s] !! BLE dropped -> reconnecting")
                client = await connect()
                await send(client, cmd_brightness(100))
                await send(client, cmd_color(*color))
            elif reassert:
                # optional: re-send the color each second (mimics an app that
                # keeps pushing state). Use --reassert to test that theory.
                try:
                    await send(client, cmd_color(*color))
                except Exception:
                    pass
            if elapsed % 10 == 0:
                print(f"  [{elapsed:5.0f}s] still holding "
                      f"(connected={client.is_connected}, drops={drops})")
        print(f"soak done: {drops} BLE drop(s) over {seconds:.0f}s")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def repl():
    """Hold one connection; type commands interactively (great for debugging)."""
    client = await connect()
    print("connected. commands: on | off | color <name|r g b> | bri <0-100> | "
          "effect <id> | speed <0-100> | raw <hex...> | quit")
    loop = asyncio.get_event_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, lambda: input("sc295> "))
            parts = line.split()
            if not parts:
                continue
            c = parts[0].lower()
            try:
                if c in ("quit", "exit", "q"):
                    break
                elif c == "on":
                    await send(client, cmd_power(True))
                elif c == "off":
                    await send(client, cmd_power(False))
                elif c == "color":
                    await send(client, cmd_color(*resolve_color(parts[1:])))
                elif c in ("bri", "brightness"):
                    await send(client, cmd_brightness(int(parts[1])))
                elif c == "effect":
                    await send(client, cmd_effect(int(parts[1], 0)))
                elif c == "speed":
                    await send(client, cmd_speed(int(parts[1])))
                elif c == "raw":
                    await send(client, parse_hex(parts[1:]))
                else:
                    print("  ? unknown command")
            except Exception as e:
                print(f"  error: {e}")
    finally:
        await client.disconnect()
        print("disconnected")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description="Control the SC295 / MELK-OA10 LED strip")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("on")
    sub.add_parser("off")

    pc = sub.add_parser("color", help="name, #rrggbb, or R G B")
    pc.add_argument("value", nargs="+")

    pb = sub.add_parser("brightness")
    pb.add_argument("pct", type=int)

    pe = sub.add_parser("effect")
    pe.add_argument("id", help="effect id (e.g. 0x87)")
    pe.add_argument("--speed", type=int, default=None)

    ps = sub.add_parser("speed")
    ps.add_argument("pct", type=int)

    pr = sub.add_parser("raw", help="send raw hex bytes to fff3")
    pr.add_argument("bytes", nargs="+")

    pm = sub.add_parser("monitor")
    pm.add_argument("seconds", type=float, nargs="?", default=15.0)

    pw = sub.add_parser("sweep", help="brightness-sweep flicker diagnostic")
    pw.add_argument("color", nargs="*", default=["blue"],
                    help="color name or R G B (default: blue)")
    pw.add_argument("--hold", type=float, default=4.0)

    pk = sub.add_parser("soak", help="hold full brightness a long time, watch for flicker")
    pk.add_argument("color", nargs="*", default=["blue"])
    pk.add_argument("--seconds", type=float, default=90.0)
    pk.add_argument("--reassert", action="store_true",
                    help="re-send the color every second (mimic app chatter)")

    sub.add_parser("repl")
    sub.add_parser("fix-connection", help="drop stale BlueZ bond")
    sub.add_parser("scan", help="scan and report the device")
    return p


def main():
    args = build_parser().parse_args()
    c = args.cmd

    if c == "fix-connection":
        _drop_bond()
        print("bond removed (if any). Next connect will re-discover fresh.")
        return
    if c == "scan":
        async def _s():
            d = await _scan_for(ADDRESS, 15)
            print(f"found: {d}" if d else "not found")
        asyncio.run(_s())
        return

    if c == "on":
        asyncio.run(run_once([cmd_power(True)]))
    elif c == "off":
        asyncio.run(run_once([cmd_power(False)]))
    elif c == "color":
        asyncio.run(run_once([cmd_color(*resolve_color(args.value))]))
    elif c == "brightness":
        asyncio.run(run_once([cmd_brightness(args.pct)]))
    elif c == "effect":
        frames = [cmd_effect(int(args.id, 0))]
        if args.speed is not None:
            frames.append(cmd_speed(args.speed))
        asyncio.run(run_once(frames))
    elif c == "speed":
        asyncio.run(run_once([cmd_speed(args.pct)]))
    elif c == "raw":
        asyncio.run(run_once([parse_hex(args.bytes)]))
    elif c == "monitor":
        asyncio.run(monitor(args.seconds))
    elif c == "sweep":
        color = resolve_color(args.color or ["blue"])
        levels = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
        asyncio.run(sweep(color, levels, args.hold))
    elif c == "soak":
        color = resolve_color(args.color or ["blue"])
        asyncio.run(soak(color, args.seconds, args.reassert))
    elif c == "repl":
        asyncio.run(repl())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
