"""Forget a BlueZ device over D-Bus: org.bluez.Adapter1.RemoveDevice(path).

Uses `dbus-fast` (already a bleak dependency on Linux) on the system bus. The
bus and the dbus_fast names are injectable so tests never touch a real bus.
"""
import asyncio
import threading

BLUEZ = "org.bluez"
DEVICE_IFACE = "org.bluez.Device1"
ADAPTER_IFACE = "org.bluez.Adapter1"
TIMEOUT = 10.0


class DbusError(RuntimeError):
    """The bus refused a call (message says which)."""


def _dbus_fast():
    import dbus_fast
    import dbus_fast.aio
    return dbus_fast


async def _system_bus(dbus):
    return await dbus.aio.MessageBus(bus_type=dbus.BusType.SYSTEM).connect()


def _value(v):
    return getattr(v, "value", v)      # dbus_fast wraps properties in Variants


async def _call(bus, dbus, **kw):
    reply = await bus.call(dbus.Message(destination=BLUEZ, **kw))
    if reply.message_type == dbus.MessageType.ERROR:
        raise DbusError(f"{kw['member']}: {reply.error_name} {reply.body}")
    return reply.body


def find_device_path(objects, address):
    """(device_path, adapter_path) for `address` in GetManagedObjects output."""
    for path, ifaces in objects.items():
        dev = ifaces.get(DEVICE_IFACE)
        if dev and str(_value(dev.get("Address", ""))).upper() == address.upper():
            return path, _value(dev.get("Adapter"))
    return None, None


async def remove_device_async(address, dbus=None, bus_factory=None):
    """True if BlueZ forgot `address`, False if it didn't know it. Raises on
    any bus failure (so the caller can fall back to bluetoothctl)."""
    dbus = dbus or _dbus_fast()
    bus = await (bus_factory or _system_bus)(dbus)
    try:
        body = await _call(bus, dbus, path="/", member="GetManagedObjects",
                           interface="org.freedesktop.DBus.ObjectManager")
        dev_path, adapter = find_device_path(body[0], address)
        if dev_path is None:
            return False
        await _call(bus, dbus, path=adapter, interface=ADAPTER_IFACE,
                    member="RemoveDevice", signature="o", body=[dev_path])
        return True
    finally:
        bus.disconnect()


def remove_device(address, timeout=TIMEOUT, **kw):
    """Blocking wrapper usable from sync code, even inside a running event
    loop: the D-Bus conversation runs on its own loop in a worker thread."""
    box = {}

    def work():
        try:
            box["ok"] = asyncio.run(
                asyncio.wait_for(remove_device_async(address, **kw), timeout))
        except BaseException as e:      # re-raised in the caller's thread
            box["err"] = e

    t = threading.Thread(target=work, name="deskglow-bluez-dbus", daemon=True)
    t.start()
    t.join(timeout + 1.0)
    if t.is_alive():
        raise DbusError("BlueZ did not answer in time")
    if "err" in box:
        raise box["err"]
    return box["ok"]
