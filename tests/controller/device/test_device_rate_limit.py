"""Rate limiting and write serialisation."""
import asyncio

from deskglow.controller import device
from device_harness import ADDR, FakeBLEDevice, connected_device, make_device
from fakes import ENCODER


async def test_back_to_back_writes_are_spaced_by_the_minimum_interval(ble, clock):
    """<=20 writes/s at the strip keeps BLE airtime tiny."""
    dev = await connected_device(ble)
    mark = ble.mark()
    frame = ENCODER.color(1, 2, 3)
    await dev.send_frame(frame)
    await dev.send_frame(frame)
    await dev.send_frame(frame)
    times = ble.times_since(mark)
    assert len(times) == 3
    for earlier, later in zip(times, times[1:], strict=False):
        assert later - earlier >= device.WRITE_MIN_INTERVAL - 1e-9


async def test_an_idle_gap_is_not_charged_against_the_rate_limit(ble, clock):
    """A write after a long idle period goes out immediately."""
    dev = await connected_device(ble)
    await dev.send_frame(ENCODER.power(True))
    clock.advance(10.0)
    before = len(clock.sleeps)
    await dev.send_frame(ENCODER.power(True))
    assert clock.sleeps[before:] == [], "slept even though the link had been idle"


async def test_concurrent_writers_never_interleave_frames(ble):
    """Overlapping modes/CLI commands must not split or braid frames on the wire
    (the fake asserts re-entrancy and whole 9-byte frames for every write)."""
    dev = await connected_device(ble)
    mark = ble.mark()
    calls = []
    for i in range(12):
        calls.append(dev.set_rgb(i, i, i, force=True))
        calls.append(dev.send_frame(ENCODER.power(bool(i % 2))))
    await asyncio.gather(*calls)

    frames = ble.frames_since(mark)
    assert len(frames) == 24
    assert all(len(f) == 9 for f in frames)
    expected = {ENCODER.color(i, i, i) for i in range(12)}
    expected |= {ENCODER.power(True), ENCODER.power(False)}
    assert set(frames) == expected


async def test_concurrent_writers_share_a_single_connection(ble):
    """A burst of concurrent calls must not open a client each."""
    ble.discoverable = [FakeBLEDevice(ADDR)]
    dev = make_device(ble)
    await asyncio.gather(*(dev.set_rgb(i, i, i, force=True) for i in range(10)))
    assert len(ble.clients) == 1
