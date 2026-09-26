"""The connect sequence: scan-free first, then a scan, then a bond reset."""
import pytest

from deskglow.controller import connect
from device_harness import ADDR, OTHER_ADDR, FakeBLEDevice, connected_device, make_device
from fakes import ENCODER


async def test_connect_tries_a_scan_free_client_before_scanning(ble):
    """A cached device must reconnect without ever starting the scanner (which
    would steal airtime from other BT devices such as a speaker)."""
    dev = make_device(ble)
    await dev.ensure_connected()
    assert ble.scans == 0
    assert len(ble.clients) == 1
    assert ble.clients[0].target == ADDR, "scan-free attempt must use the raw MAC"
    assert ble.clients[0].timeout == connect.CACHED_TIMEOUT
    assert dev.connected


async def test_connect_falls_back_to_a_scan_and_uses_the_scanned_device(ble):
    """When the scan-free connect fails we scan, then connect to the *device
    object* the scan produced (not the bare MAC again)."""
    scanned = FakeBLEDevice(ADDR)
    ble.discoverable = [scanned]
    ble.connect_errors = [OSError("not cached")]
    dev = make_device(ble)
    await dev.ensure_connected()
    assert ble.scans == 1
    assert [c.target for c in ble.clients] == [ADDR, scanned]
    assert ble.clients[1].timeout == connect.SCANNED_TIMEOUT
    assert dev.connected


async def test_connect_ignores_devices_with_a_different_address(ble):
    """The scan must only accept our strip, not the neighbour's."""
    ble.discoverable = [FakeBLEDevice(OTHER_ADDR)]
    ble.connect_errors = [OSError("not cached")]
    dev = make_device(ble)
    with pytest.raises(ConnectionError, match="not found in scan"):
        await dev.ensure_connected()


async def test_connect_raises_when_the_device_is_not_found_in_the_scan(ble):
    """Nothing discovered => a ConnectionError naming the address."""
    ble.discoverable = []
    ble.connect_errors = [OSError("not cached")]
    dev = make_device(ble)
    with pytest.raises(ConnectionError, match=f"{ADDR} not found in scan"):
        await dev.ensure_connected()
    assert ble.scans == 1


async def test_connect_drops_a_stale_bond_and_retries_once(ble, logs):
    """The BlueZ 'bonded device => ServicesResolved hangs' quirk: after the
    post-scan connect fails we remove the bond and try one more time."""
    scanned = FakeBLEDevice(ADDR)
    ble.discoverable = [scanned]
    ble.connect_errors = [OSError("not cached"), OSError("ServicesResolved timeout")]
    dev = make_device(ble, logs)
    await dev.ensure_connected()
    assert ble.dropped_bonds == [ADDR], "bond must be dropped for the strip's MAC"
    assert ble.scans == 2, "must re-scan after dropping the bond"
    assert [c.target for c in ble.clients] == [ADDR, scanned, scanned]
    assert any("clearing bond" in m for m in logs)
    assert dev.connected


async def test_connect_gives_up_when_the_device_vanishes_after_the_bond_reset(ble):
    """If the strip disappears once the bond is cleared, say so plainly."""
    ble.scan_results = [[FakeBLEDevice(ADDR)], []]   # found, then gone
    ble.connect_errors = [OSError("not cached"), OSError("ServicesResolved timeout")]
    dev = make_device(ble)
    with pytest.raises(ConnectionError, match="vanished after bond reset"):
        await dev.ensure_connected()
    assert ble.dropped_bonds == [ADDR]
    assert ble.scans == 2


async def test_failed_connect_disconnects_the_doomed_client(ble):
    """A session whose connect() raised still holds a system D-Bus connection;
    not releasing it leaks one per attempt until all Bluetooth breaks."""
    ble.fail_connects()
    with pytest.raises(OSError):
        await connect.open_session(ble, ADDR, 6.0)
    assert len(ble.clients) == 1
    assert ble.clients[0].disconnect_calls == 1, "leaked the failed client"


async def test_successful_client_is_not_disconnected(ble):
    """The happy path must obviously not tear down the link it just built."""
    client = await connect.open_session(ble, ADDR, 6.0)
    assert client.disconnect_calls == 0
    assert client.is_connected


async def test_connect_pins_power_on_and_full_brightness(ble, logs):
    """Modes modulate brightness via RGB, so the strip itself is pinned on at
    100% the moment the link comes up."""
    dev = make_device(ble, logs)
    await dev.ensure_connected()
    assert ble.frames_since((0, 0, 0)) == [ENCODER.power(True), ENCODER.brightness(100)]
    assert ble.frames_since((0, 0, 0)) == [
        bytes.fromhex("7E 00 04 F0 00 01 FF 00 EF"), bytes.fromhex("7E 00 01 64 00 00 00 00 EF")]
    assert ble.responses_since((0, 0, 0)) == [False, False]
    assert any("connected" in msg for msg in logs)


async def test_connect_resets_the_dedup_cache(ble):
    """A strip that dropped the link has forgotten its colour, so the de-dup
    cache must be cleared or the next set_rgb would be wrongly skipped."""
    dev = await connected_device(ble)
    await dev.set_rgb(1, 2, 3)
    assert dev.last_rgb == (1, 2, 3)

    ble.clients[-1].is_connected = False        # link dropped under us
    await dev.ensure_connected()
    assert dev.last_rgb is None, "stale de-dup cache survived a reconnect"
