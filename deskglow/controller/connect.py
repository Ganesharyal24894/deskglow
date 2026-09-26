"""The connect sequence for one strip, expressed against the LightLink service.

Be a good neighbour to other BT devices (e.g. a speaker): never keep an active
scan running; try a scan-free reconnect first and only fall back to a short
scan when the device isn't in the stack's cache. Recover from the "bonded
device => service resolution hangs" BlueZ quirk by dropping the stale bond and
retrying once.
"""
import asyncio
import contextlib

from ..model.settings import SCAN_TIMEOUT

CACHED_TIMEOUT = 6.0       # scan-free connect to a cached device
SCANNED_TIMEOUT = 20.0     # connect after a scan found the device
SETTLE = 0.3               # pause between a scan and the connect it enables


async def open_session(link, target, timeout):
    """Connect a fresh session; on failure, release its resources.

    Failing to disconnect a session whose connect() raised leaks a system D-Bus
    connection each time on BlueZ; after ~256 (the per-user bus limit) ALL
    Bluetooth breaks. So we always clean up on the failure path."""
    c = link.session(target, timeout)
    try:
        await c.connect()
        return c
    except Exception:
        with contextlib.suppress(Exception):
            await c.disconnect()
        raise


async def connect_strip(link, address, log):
    """Return a connected session to `address`, or raise ConnectionError/OSError."""
    if not address:
        raise ConnectionError("no strip configured — run 'deskglow setup'")
    # 1) scan-free reconnect (no speaker interference) if the stack still knows
    #    it. Short timeout: a cached device connects in <2s; we don't want to
    #    freeze a running mode when this path isn't going to work.
    with contextlib.suppress(Exception):
        return await open_session(link, address, CACHED_TIMEOUT)
    # 2) short scan to (re)discover, then connect
    dev = await link.find(address, SCAN_TIMEOUT)
    if dev is None:
        raise ConnectionError(f"{address} not found in scan")
    await asyncio.sleep(SETTLE)
    try:
        return await open_session(link, dev, SCANNED_TIMEOUT)
    except Exception as e:
        # 3) stale bond blocking service resolution -> drop and retry once
        log(f"connect failed ({type(e).__name__}); clearing bond, retrying")
        link.drop_bond(address)
        dev = await link.find(address, SCAN_TIMEOUT)
        if dev is None:
            raise ConnectionError("device vanished after bond reset") from e
        await asyncio.sleep(SETTLE)
        return await open_session(link, dev, SCANNED_TIMEOUT)
