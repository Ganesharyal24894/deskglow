"""set_rgb: de-duplication, the ~2s keepalive and the ~12s verify write."""
from device_harness import connected_device
from fakes import ENCODER


async def test_identical_colour_inside_the_keepalive_window_writes_once(ble, clock):
    """Repeating a colour costs no BLE airtime."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.set_rgb(10, 20, 30)
    clock.advance(0.5)
    await dev.set_rgb(10, 20, 30)
    clock.advance(0.5)
    await dev.set_rgb(10, 20, 30)
    assert ble.frames_since(mark) == [ENCODER.color(10, 20, 30)]


async def test_a_changed_colour_always_writes(ble, clock):
    """De-duplication must never swallow an actual colour change."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.set_rgb(10, 20, 30)
    clock.advance(0.01)
    await dev.set_rgb(10, 20, 31)
    clock.advance(0.01)
    await dev.set_rgb(0, 0, 0)
    assert ble.frames_since(mark) == [
        ENCODER.color(10, 20, 30), ENCODER.color(10, 20, 31), ENCODER.color(0, 0, 0)]


async def test_identical_colour_is_reasserted_after_two_seconds(ble, clock):
    """A ~2s keepalive re-asserts the colour so a strip that lost it recovers."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.set_rgb(10, 20, 30)
    clock.advance(1.9)
    await dev.set_rgb(10, 20, 30)
    assert ble.frames_since(mark) == [ENCODER.color(10, 20, 30)], "re-asserted too early"
    clock.advance(0.2)
    await dev.set_rgb(10, 20, 30)
    assert ble.frames_since(mark) == [ENCODER.color(10, 20, 30)] * 2


async def test_force_always_writes_even_for_an_identical_colour(ble, clock):
    """force=True is the escape hatch when the strip's state is unknown."""
    dev = await connected_device(ble)
    mark = ble.mark()
    await dev.set_rgb(10, 20, 30)
    clock.advance(0.05)
    await dev.set_rgb(10, 20, 30, force=True)
    clock.advance(0.05)
    await dev.set_rgb(10, 20, 30, force=True)
    assert ble.frames_since(mark) == [ENCODER.color(10, 20, 30)] * 3


async def test_a_verify_write_is_acknowledged_about_every_twelve_seconds(ble, clock):
    """A write-without-response cannot tell a live link from a dead one, so
    every ~12s one write asks for an ack; the rest stay unacknowledged."""
    dev = await connected_device(ble)
    mark = ble.mark()

    await dev.set_rgb(1, 1, 1)                      # first ever write: verify
    assert ble.responses_since(mark) == [True]

    for _ in range(5):                              # ~10s of ordinary traffic
        clock.advance(2.0)
        await dev.set_rgb(1, 1, 1)
    assert ble.responses_since(mark) == [True, False, False, False, False, False]

    clock.advance(2.1)                              # crosses the 12s mark
    await dev.set_rgb(1, 1, 1)
    assert ble.responses_since(mark)[-1] is True

    clock.advance(2.0)
    await dev.set_rgb(1, 1, 1)
    assert ble.responses_since(mark)[-1] is False


async def test_the_verify_tick_is_never_skipped_by_de_duplication(ble, clock):
    """Liveness must still be checked while the colour is static — otherwise a
    dead link on a solid colour is never noticed."""
    dev = await connected_device(ble)
    await dev.set_rgb(7, 7, 7)          # consumes the initial verify
    clock.advance(0.1)
    mark = ble.mark()
    clock.advance(12.0)
    await dev.set_rgb(7, 7, 7)          # identical, but a verify is due
    assert ble.responses_since(mark) == [True]
