"""BLE connection layer for the strip.

Design goals:
  * Hold at most ONE connection; reconnect transparently if it drops.
  * Be a good neighbour to other BT devices (e.g. a speaker): never keep an
    active scan running; try a scan-free reconnect first and only fall back to a
    short scan when the device isn't in BlueZ's cache.
  * Recover from the "bonded device => ServicesResolved hangs" BlueZ quirk by
    dropping the stale bond and retrying.
  * Rate-limit and de-duplicate writes so BLE airtime stays tiny.
"""
import asyncio
import contextlib
import subprocess
import time

from bleak import BleakScanner, BleakClient

from . import protocol
from .config import SCAN_TIMEOUT, WRITE_MIN_INTERVAL, get_address

log = print  # replaced by daemon with a real logger


async def _scan_for(address, timeout):
    fut = asyncio.get_event_loop().create_future()

    def cb(dev, _adv):
        if dev.address.upper() == address.upper() and not fut.done():
            fut.set_result(dev)

    async with BleakScanner(detection_callback=cb):
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except asyncio.TimeoutError:
            return None
    # scanner context exit stops discovery -> frees the radio for the speaker


def _drop_bond(address):
    try:
        subprocess.run(["bluetoothctl", "remove", address],
                       capture_output=True, timeout=10)
    except Exception:
        pass


class Device:
    def __init__(self, address=None, logger=None):
        self._explicit_address = address  # None => read from config each time
        self._client = None
        self._lock = asyncio.Lock()
        self._last_write = 0.0
        self._last_rgb = None
        self._last_send_ts = 0.0
        self._cooldown_until = 0.0
        self._fail_count = 0
        if logger:
            global log
            log = logger

    @property
    def address(self):
        """Current strip MAC (explicit override, else the saved config)."""
        return self._explicit_address or get_address()

    @property
    def connected(self):
        return self._client is not None and self._client.is_connected

    def in_cooldown(self):
        return time.monotonic() < self._cooldown_until

    @property
    def consecutive_failures(self):
        return self._fail_count

    def reset_backoff(self):
        """Clear the connect cooldown/failure count (e.g. after (re)configuring
        the address) so the next attempt happens immediately."""
        self._cooldown_until = 0.0
        self._fail_count = 0

    @staticmethod
    async def _try_client(target, timeout):
        """Connect a fresh client; on failure, release its D-Bus/socket resources.

        Failing to disconnect a client whose connect() raised leaks a system
        D-Bus connection each time; after ~256 (the per-user bus limit) ALL
        Bluetooth breaks. So we always clean up on the failure path."""
        c = BleakClient(target, timeout=timeout)
        try:
            await c.connect()
            return c
        except Exception:
            with contextlib.suppress(Exception):
                await c.disconnect()
            raise

    async def _raw_connect(self):
        address = self.address
        if not address:
            raise ConnectionError("no strip configured — run 'sc295 setup'")
        # 1) scan-free reconnect (no speaker interference) if BlueZ still knows it.
        #    Short timeout: a cached device connects in <2s; we don't want to
        #    freeze a running mode for 12s when this path isn't going to work.
        with contextlib.suppress(Exception):
            return await self._try_client(address, 6.0)
        # 2) short scan to (re)discover, then connect
        dev = await _scan_for(address, SCAN_TIMEOUT)
        if dev is None:
            raise ConnectionError(f"{address} not found in scan")
        await asyncio.sleep(0.3)
        try:
            return await self._try_client(dev, 20.0)
        except Exception as e:
            # 3) stale bond blocking service resolution -> drop and retry once
            log(f"connect failed ({type(e).__name__}); clearing bond, retrying")
            _drop_bond(address)
            dev = await _scan_for(address, SCAN_TIMEOUT)
            if dev is None:
                raise ConnectionError("device vanished after bond reset")
            await asyncio.sleep(0.3)
            return await self._try_client(dev, 20.0)

    async def ensure_connected(self):
        async with self._lock:
            if self.connected:
                return
            # Back off when the strip is unreachable so we don't scan the radio
            # continuously (which would disrupt other BT devices like a speaker).
            if time.monotonic() < self._cooldown_until:
                raise ConnectionError("strip unreachable (in connect cooldown)")
            try:
                self._client = await self._raw_connect()
                # Modes modulate brightness via RGB, so pin device brightness at
                # 100 and make sure the strip is powered on.
                await self._client.write_gatt_char(
                    protocol.WRITE_UUID, protocol.power(True), response=False)
                await self._client.write_gatt_char(
                    protocol.WRITE_UUID, protocol.brightness(100), response=False)
                self._last_rgb = None
                self._fail_count = 0
                log("connected to strip")
            except Exception:
                self._client = None
                self._fail_count += 1
                # ramp to a long backoff so a strip that's simply off/away isn't
                # retried hundreds of times overnight (5s -> up to 5min)
                backoff = min(300.0, 5.0 * self._fail_count)
                self._cooldown_until = time.monotonic() + backoff
                if self._fail_count <= 2 or self._fail_count % 5 == 0:
                    log(f"connect failed (x{self._fail_count}); "
                        f"backing off {backoff:.0f}s")
                raise

    async def disconnect(self):
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None
                self._last_rgb = None
                log("disconnected from strip")

    async def _write(self, frame, response=False):
        # rate limit
        dt = time.monotonic() - self._last_write
        if dt < WRITE_MIN_INTERVAL:
            await asyncio.sleep(WRITE_MIN_INTERVAL - dt)
        # ensure_connected raises quickly while in backoff (no scan, no spam) and
        # otherwise makes at most one connection attempt.
        await self.ensure_connected()
        try:
            await self._client.write_gatt_char(
                protocol.WRITE_UUID, frame, response=response)
            self._last_write = time.monotonic()
        except Exception:
            self._client = None  # drop; next call reconnects (no cooldown yet)
            raise

    async def set_rgb(self, r, g, b, force=False):
        rgb = (int(r), int(g), int(b))
        now = time.monotonic()
        # de-dup identical colors, but re-assert every ~2s as a keepalive
        if (not force and rgb == self._last_rgb
                and now - self._last_send_ts < 2.0):
            return
        await self._write(protocol.color(*rgb))
        self._last_rgb = rgb
        self._last_send_ts = now

    async def power(self, on, reliable=False):
        await self._write(protocol.power(on), response=reliable)

    async def send_frame(self, frame, reliable=False):
        await self._write(frame, response=reliable)

    async def reset_known_good(self):
        """Force a known-good static state: power on, full brightness, solid
        white, using reliable (with-response) writes to break any effect/blink
        mode a physical-button press may have left the strip in."""
        await self.send_frame(protocol.power(True), reliable=True)
        await self.send_frame(protocol.brightness(100), reliable=True)
        await self.send_frame(protocol.color(255, 255, 255), reliable=True)
        await self.send_frame(protocol.color(255, 255, 255), reliable=True)
