"""drivers.bluez_dbus: RemoveDevice over a scripted fake system bus."""
import pytest
from dbus_fakes import DBUS, FakeBus, Variant, reply

from deskglow.drivers import bluez, bluez_dbus

ADDR = "AA:BB:CC:DD:EE:FF"
DEV = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
OBJECTS = {
    "/org/bluez/hci0": {"org.bluez.Adapter1": {"Address": Variant("s", "00:11:22:33:44:55")}},
    "/org/bluez/hci0/dev_11_22": {"org.bluez.Device1": {
        "Address": Variant("s", "11:22:33:44:55:66"), "Adapter": Variant("o", "/org/bluez/hci0")}},
    DEV: {"org.bluez.Device1": {"Address": Variant("s", ADDR),
                                "Adapter": Variant("o", "/org/bluez/hci0")}},
}


def script(objects=OBJECTS, remove_error=None):
    def answer(bus, msg):
        if msg.member == "GetManagedObjects":
            return reply([objects])
        if msg.member == "RemoveDevice":
            return reply(error=remove_error)
        raise AssertionError(msg.member)
    return answer


async def run(bus, address=ADDR):
    async def factory(dbus):
        assert dbus is DBUS
        return bus
    return await bluez_dbus.remove_device_async(address, dbus=DBUS, bus_factory=factory)


async def test_removes_the_matching_device_through_its_adapter():
    bus = FakeBus(script())
    assert await run(bus, ADDR.lower()) is True
    get, remove = bus.calls
    assert (get.destination, get.path, get.interface) == (
        "org.bluez", "/", "org.freedesktop.DBus.ObjectManager")
    assert (remove.path, remove.interface, remove.member) == (
        "/org/bluez/hci0", "org.bluez.Adapter1", "RemoveDevice")
    assert (remove.signature, remove.body) == ("o", [DEV])
    assert bus.disconnected == 1


async def test_an_unknown_device_is_not_an_error_and_removes_nothing():
    bus = FakeBus(script())
    assert await run(bus, "01:02:03:04:05:06") is False
    assert [m.member for m in bus.calls] == ["GetManagedObjects"]
    assert bus.disconnected == 1


async def test_a_refused_removal_raises_and_still_disconnects():
    bus = FakeBus(script(remove_error="org.bluez.Error.NotAuthorized"))
    with pytest.raises(bluez_dbus.DbusError, match="NotAuthorized"):
        await run(bus)
    assert bus.disconnected == 1


def test_blocking_wrapper_works_inside_a_running_loop():
    """drop_bond is sync but may be called from the daemon's event loop."""
    import asyncio
    bus = FakeBus(script())

    async def factory(dbus):
        return bus

    async def main():
        return bluez_dbus.remove_device(ADDR, dbus=DBUS, bus_factory=factory)
    assert asyncio.run(main()) is True


def test_blocking_wrapper_reraises_bus_failures():
    async def factory(dbus):
        raise ConnectionRefusedError("no system bus")
    with pytest.raises(ConnectionRefusedError):
        bluez_dbus.remove_device(ADDR, dbus=DBUS, bus_factory=factory)


def test_drop_bond_uses_dbus_end_to_end_without_bluetoothctl(monkeypatch):
    bus = FakeBus(script())

    async def factory(dbus):
        return bus
    ran = []
    monkeypatch.setattr(bluez, "_remove_with_bluetoothctl", ran.append)
    bluez.drop_bond(ADDR, dbus_remove=lambda a: bluez_dbus.remove_device(
        a, dbus=DBUS, bus_factory=factory))
    assert [m.member for m in bus.calls] == ["GetManagedObjects", "RemoveDevice"]
    assert ran == []
