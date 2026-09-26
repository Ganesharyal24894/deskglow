"""A failed write drops (and releases) the session so the next call reconnects."""
import pytest

from device_harness import connected_device, make_device


async def test_a_failed_write_drops_the_client_so_the_next_call_reconnects(ble):
    """A dead link must not keep reporting connected==True."""
    dev = await connected_device(ble)
    ble.write_error = OSError("Not connected")
    with pytest.raises(OSError):
        await dev.power(True)
    assert dev.connected is False

    ble.write_error = None
    mark = ble.mark()
    await dev.power(True)
    assert ble.clients_since(mark), "did not reconnect after the failed write"
    assert dev.connected is True


async def test_a_failed_write_releases_the_clients_resources(ble):
    """Dropping the reference to a *connected* session without disconnecting it
    leaks exactly the D-Bus connection the module docstring says we must never
    leak — and this path runs every time the verify write finds a dead link."""
    dev = await connected_device(ble)
    doomed = ble.clients[-1]
    ble.write_error = OSError("Not connected")
    with pytest.raises(OSError):
        await dev.power(True)
    assert doomed.disconnect_calls == 1, "leaked the client of a failed write"


async def test_a_failed_pin_write_releases_the_clients_resources(ble):
    """Same leak on the connect path: if the pin writes fail we null out a
    freshly connected session instead of closing it."""
    ble.write_error = OSError("Not connected")
    dev = make_device(ble)
    with pytest.raises(OSError):
        await dev.ensure_connected()
    assert ble.clients[-1].disconnect_calls == 1, "leaked the client of a failed pin write"
    assert dev.consecutive_failures == 1
