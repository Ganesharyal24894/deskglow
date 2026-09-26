"""`deskglow setup`: scan for strips, let the user pick one, save it, test it."""
import asyncio
import sys

from .cli_parser import PROG


def _choose(cands):
    if len(cands) == 1:
        chosen = cands[0]
        print(f"Found your strip: {chosen['name']}  ({chosen['address']})")
        return chosen
    print("Found these — pick the one that's your strip:")
    for i, c in enumerate(cands, 1):
        hint = "  ← likely" if c["certain"] else ""
        print(f"  {i}. {c['name']:<20} {c['address']}  signal {c['rssi']}dBm{hint}")
    try:
        sel = input(f"\nWhich one? [1-{len(cands)}, default 1]: ").strip() or "1"
        return cands[int(sel) - 1]
    except (ValueError, IndexError, EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return None


def run_setup(cli):
    """Scan for LED strips, let the user pick one, save it, and reconnect."""
    print("Scanning for LED strips… (make sure the strip is plugged in, nearby,")
    print("and NOT connected to the phone app)\n")
    try:
        cands = cli.scan(timeout=10.0)
    except Exception as e:
        print(f"Scan failed: {e}\nIs Bluetooth turned on?", file=sys.stderr)
        return 1
    if not cands:
        print("No LED strips found. Turn the strip on, keep it close, close the")
        print(f"phone app, and run  {PROG} setup  again.")
        return 1
    chosen = _choose(cands)
    if chosen is None:
        return 1
    cli.settings.set_address(chosen["address"], chosen.get("name"))
    print(f"\nSaved: {chosen['address']}")
    print("Testing — the strip should turn WHITE for a moment…")
    asyncio.run(cli.send({"cmd": "reload"}))
    asyncio.run(cli.send({"cmd": "set_mode", "mode": "solid",
                          "args": {"rgb": [255, 255, 255]}}))
    print(f"\nDone! If the strip turned white, you're set. Try:  {PROG} on")
    return 0
