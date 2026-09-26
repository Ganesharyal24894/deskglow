"""Device.disconnect: release the radio cleanly, whatever the session does."""
from device_harness import connected_device, make_device
from fakes import ENCODER


async def test_disconnect_closes_the_client_and_clears_state(ble, logs):
    """Releasing the radio is what lets a BT speaker have it back."""
    dev = await connected_device(ble, logs=logs)
    await dev.set_rgb(1, 2, 3)
    client = ble.clients[-1]
    await dev.disconnect()
    assert client.disconnect_calls == 1
    assert dev.connected is False
    assert dev.last_rgb is None
    assert any("disconnected" in msg for msg in logs)


async def test_disconnect_is_safe_when_never_connected(ble, logs):
    """Called on a Device that never connected it is a silent no-op."""
    dev = make_device(ble, logs)
    await dev.disconnect()
    await dev.disconnect()
    assert dev.connected is False
    assert ble.clients == []
    assert not any("disconnected" in msg for msg in logs)


async def test_disconnect_survives_a_client_that_raises(ble):
    """A wedged BlueZ session must not stop us dropping our reference to it."""
    dev = await connected_device(ble)
    client = ble.clients[-1]

    async def boom():
        raise OSError("dbus gone")

    client.disconnect = boom
    await dev.disconnect()
    assert dev.connected is False


async def test_a_reconnect_after_disconnect_pins_the_strip_again(ble):
    """The strip forgets everything when the link drops."""
    dev = await connected_device(ble)
    await dev.disconnect()
    mark = ble.mark()
    await dev.ensure_connected()
    assert ble.frames_since(mark) == [ENCODER.power(True), ENCODER.brightness(100)]
