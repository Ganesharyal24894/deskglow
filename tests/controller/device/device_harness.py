"""A fake BLE world for controller.device / controller.connect tests.

The LightLink service is replaced by FakeBle (sessions, targeted scans, bond
drops), and the modules' clock and sleeps by a fake clock, so the rate limiter,
keepalive and connect backoff run instantly and deterministically.
"""
import asyncio

import pytest

from deskglow.controller import device
from fakes import ENCODER

ADDR = "AA:BB:CC:DD:EE:FF"
OTHER_ADDR = "11:22:33:44:55:66"


class FakeBLEDevice:
    """Stand-in for the handle a targeted scan hands back."""

    def __init__(self, address=ADDR, name="strip"):
        self.address = address
        self.name = name

    def __repr__(self):
        return f"<FakeBLEDevice {self.address}>"


class FakeSession:
    """A LinkSession: records connects, disconnects and writes."""

    def __init__(self, target, timeout, ble):
        self.target = target
        self.timeout = timeout
        self.ble = ble
        self.is_connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.writes = []          # [(frame, response, t)]

    async def connect(self):
        self.connect_calls += 1
        exc = self.ble.next_connect_error()
        if exc is not None:
            raise exc
        self.is_connected = True

    async def disconnect(self):
        self.disconnect_calls += 1
        self.is_connected = False

    async def write(self, frame, response=False):
        ble = self.ble
        # Re-entrancy guard: two frames must never be in flight at once, and a
        # frame must always arrive whole (never split or merged with another).
        assert not ble._writing, "frames interleaved: write re-entered"
        ble._writing = True
        try:
            assert len(frame) == 9, f"not a whole 9-byte frame: {bytes(frame)!r}"
            await asyncio.sleep(0)  # a real yield point, so a broken lock shows up
            record = (bytes(frame), response, ble.clock.now)
            self.writes.append(record)
            ble.writes.append(record)
            if ble.write_error is not None:
                raise ble.write_error
        finally:
            ble._writing = False


class FakeBle:
    """The LightLink service for one test; records what happened."""

    def __init__(self, clock):
        self.clock = clock
        self.clients = []             # every FakeSession ever constructed
        self.writes = []              # (frame, response, t) across sessions
        self.scans = 0                # find() calls
        self.connect_errors = []      # consumed in order, then default_connect_error
        self.default_connect_error = None
        self.write_error = None
        self.discoverable = []        # what every scan will "find"
        self.scan_results = []        # per-scan overrides, consumed in order
        self.dropped_bonds = []
        self._writing = False

    # -- LightLink -------------------------------------------------------

    def session(self, target, timeout):
        c = FakeSession(target, timeout, self)
        self.clients.append(c)
        return c

    async def find(self, address, timeout):
        self.scans += 1
        found = self.scan_results.pop(0) if self.scan_results else self.discoverable
        for dev in found:
            if dev.address.upper() == address.upper():
                return dev
        return None

    def drop_bond(self, address):
        self.dropped_bonds.append(address)

    # -- helpers ---------------------------------------------------------

    def next_connect_error(self):
        if self.connect_errors:
            return self.connect_errors.pop(0)
        return self.default_connect_error

    def fail_connects(self, exc=None):
        self.default_connect_error = exc or OSError("le-connection-abort-by-local")

    def mark(self):
        """Snapshot counters so a test can assert on what happens next."""
        return (len(self.writes), len(self.clients), self.scans)

    def frames_since(self, mark):
        return [w[0] for w in self.writes[mark[0]:]]

    def responses_since(self, mark):
        return [w[1] for w in self.writes[mark[0]:]]

    def times_since(self, mark):
        return [w[2] for w in self.writes[mark[0]:]]

    def clients_since(self, mark):
        return self.clients[mark[1]:]


def make_device(ble, logs=None, address=ADDR, address_source=None):
    return device.Device(ble, ENCODER, address=address, address_source=address_source,
                         logger=(logs.append if logs is not None else (lambda _m: None)))


async def connected_device(ble, address=ADDR, logs=None):
    """A Device with a live (fake) link, ready for write assertions."""
    ble.discoverable = [FakeBLEDevice(address)]
    dev = make_device(ble, logs, address=address)
    await dev.ensure_connected()
    return dev


async def expect_failed_connect(dev):
    with pytest.raises(ConnectionError):
        await dev.ensure_connected()
