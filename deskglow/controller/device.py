"""Connection policy for one strip, expressed against the LightLink service.

Design goals:
  * Hold at most ONE connection; reconnect transparently if it drops.
  * Be a good neighbour to other BT devices: back off when the strip is away,
    and connect via the scan-light sequence in controller.connect.
  * Rate-limit and de-duplicate writes so BLE airtime stays tiny.
  * Never let go of a session without disconnecting it: on BlueZ each leaked
    session is a system D-Bus connection, and ~256 of them break ALL Bluetooth.
"""
import asyncio
import contextlib
import logging
import time

from ..model.settings import WRITE_MIN_INTERVAL
from .connect import connect_strip

_default_log = logging.getLogger("deskglow.device").info

BACKOFF_STEP = 5.0         # seconds added to the cooldown per consecutive failure
BACKOFF_MAX = 300.0        # never wait longer than 5 minutes between attempts
VERIFY_EVERY = 12.0        # seconds between acknowledged (liveness) writes
KEEPALIVE = 2.0            # re-assert an unchanged colour this often


class Device:
    def __init__(self, link, encoder, address=None, address_source=None, logger=None):
        self.link = link
        self.encoder = encoder
        self._explicit_address = address       # None => ask address_source each time
        self._address_source = address_source or (lambda: None)
        self._log = logger or _default_log
        self._client = None
        self._lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()  # one frame at a time, in order
        self._last_write = 0.0
        self._last_rgb = None
        self._last_send_ts = 0.0
        self._last_verify_ts = 0.0
        self._cooldown_until = 0.0
        self._fail_count = 0

    @property
    def address(self):
        """Current strip MAC (explicit override, else the configured one)."""
        return self._explicit_address or self._address_source()

    @property
    def last_rgb(self):
        """The last colour written to the strip, or None if unknown."""
        return self._last_rgb

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

    async def ensure_connected(self):
        async with self._lock:
            if self.connected:
                return
            # Back off when the strip is unreachable so we don't scan the radio
            # continuously (which would disrupt other BT devices like a speaker).
            if time.monotonic() < self._cooldown_until:
                raise ConnectionError("strip unreachable (in connect cooldown)")
            client = None
            try:
                client = await connect_strip(self.link, self.address, self._log)
                # Modes modulate brightness via RGB, so pin device brightness at
                # 100 and make sure the strip is powered on.
                await client.write(self.encoder.power(True), response=False)
                await client.write(self.encoder.brightness(100), response=False)
                self._client = client
                self._last_rgb = None
                self._fail_count = 0
                self._log("connected to strip")
            except Exception:
                # if we got a live session and then failed, hand it back first
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()
                self._client = None
                self._fail_count += 1
                # ramp to a long backoff so a strip that's simply off/away isn't
                # retried hundreds of times overnight (5s -> up to 5min)
                backoff = min(BACKOFF_MAX, BACKOFF_STEP * self._fail_count)
                self._cooldown_until = time.monotonic() + backoff
                if self._fail_count <= 2 or self._fail_count % 5 == 0:
                    self._log(f"connect failed (x{self._fail_count}); "
                              f"backing off {backoff:.0f}s")
                raise

    async def disconnect(self):
        async with self._lock:
            if self._client is not None:
                with contextlib.suppress(Exception):
                    await self._client.disconnect()
                self._client = None
                self._last_rgb = None
                self._log("disconnected from strip")

    async def _write(self, frame, response=False):
        # Serialize writers: concurrent callers must not interleave frames or
        # race the rate limiter (which would burst writes at the strip).
        async with self._write_lock:
            dt = time.monotonic() - self._last_write
            if dt < WRITE_MIN_INTERVAL:
                await asyncio.sleep(WRITE_MIN_INTERVAL - dt)
            # ensure_connected raises quickly while in backoff (no scan, no spam)
            # and otherwise makes at most one connection attempt.
            await self.ensure_connected()
            try:
                await self._client.write(frame, response=response)
                self._last_write = time.monotonic()
            except Exception:
                # Drop the link so the next call reconnects (no cooldown yet) —
                # but disconnect it first (the leak rule in the module docstring;
                # the periodic acknowledged write exists precisely to hit this).
                client, self._client = self._client, None
                if client is not None:
                    with contextlib.suppress(Exception):
                        await client.disconnect()
                raise

    async def set_rgb(self, r, g, b, force=False):
        rgb = (int(r), int(g), int(b))
        now = time.monotonic()
        # Periodically use an ACKNOWLEDGED write: a write-without-response can't
        # tell a live link from a dead one, so a silently-dropped strip would
        # keep reporting "connected" while nothing works.
        verify = (now - self._last_verify_ts) >= VERIFY_EVERY
        # de-dup identical colors, but re-assert every ~2s as a keepalive (and
        # never skip a verify tick, so liveness is checked even on a static color)
        if (not force and not verify and rgb == self._last_rgb
                and now - self._last_send_ts < KEEPALIVE):
            return
        await self._write(self.encoder.color(*rgb), response=verify)
        self._last_rgb = rgb
        self._last_send_ts = now
        if verify:
            self._last_verify_ts = now

    async def power(self, on, reliable=False):
        await self._write(self.encoder.power(on), response=reliable)

    async def send_frame(self, frame, reliable=False):
        await self._write(frame, response=reliable)

    async def reset_known_good(self):
        """Force a known-good static state: power on, full brightness, solid
        white, using reliable (with-response) writes to break any effect/blink
        mode a physical-button press may have left the strip in."""
        enc = self.encoder
        await self.send_frame(enc.power(True), reliable=True)
        await self.send_frame(enc.brightness(100), reliable=True)
        await self.send_frame(enc.color(255, 255, 255), reliable=True)
        await self.send_frame(enc.color(255, 255, 255), reliable=True)
