"""LightLink and Scanner on top of `bleak` (BlueZ, CoreBluetooth, WinRT).

bleak must only ever run in the daemon process: on Windows its WinRT backend
needs the thread's COM apartment to be MTA, which a GUI toolkit would change.
"""
import asyncio
import re

from ..services.link import AdapterError
from ..services.scanner import Advert
from . import bluez

_MAC = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$", re.I)


class NoAdapterAdmin:
    """Bond/adapter housekeeping where the OS owns it (macOS, Windows)."""

    def drop_bond(self, address):
        """Nothing to do: these OSes never bond an unauthenticated strip."""

    def reset_adapter(self, address):
        raise AdapterError(
            "Resetting the Bluetooth adapter is not supported on this OS. Turn "
            "Bluetooth off and on again in the system settings, then retry.")


def _bleak():
    import bleak
    return bleak


class BleakSession:
    """One BleakClient connection attempt, writing to the preset's characteristic."""

    def __init__(self, target, timeout, write_uuid, client_factory=None):
        factory = client_factory or _bleak().BleakClient
        self._client = factory(target, timeout=timeout)
        self._write_uuid = write_uuid

    @property
    def is_connected(self):
        return self._client.is_connected

    async def connect(self):
        await self._client.connect()

    async def write(self, frame, response=False):
        await self._client.write_gatt_char(self._write_uuid, frame, response=response)

    async def disconnect(self):
        await self._client.disconnect()


class BleakLink:
    """LightLink: sessions via BleakClient, targeted scans via BleakScanner."""

    def __init__(self, write_uuid, client_factory=None, scanner_factory=None, admin=bluez,
                 saved_name=None):
        """`saved_name` (macOS): a callable returning the strip's saved name.
        CoreBluetooth addresses are per-Mac UUIDs, so an address saved on
        another machine never matches; the scan then settles for the name."""
        self.write_uuid = write_uuid
        self._client_factory = client_factory
        self._scanner_factory = scanner_factory
        self._admin = admin
        self._saved_name = saved_name

    def session(self, target, timeout):
        return BleakSession(target, timeout, self.write_uuid, self._client_factory)

    def _fallback_name(self, address):
        if self._saved_name is None:
            return None
        try:
            return self._saved_name() or None
        except Exception:
            return None

    async def find(self, address, timeout):
        """Scan for `address`. With a saved name (macOS), a device advertising
        that name is used if the address never shows up; when the saved
        address is a MAC (which CoreBluetooth never reports) it is used at once."""
        fut = asyncio.get_running_loop().create_future()
        name = self._fallback_name(address)
        by_name = []
        name_is_final = bool(name) and bool(_MAC.match(address))

        def cb(dev, adv):
            if fut.done():
                return
            if dev.address.upper() == address.upper():
                fut.set_result(dev)
            elif name and name in (dev.name, getattr(adv, "local_name", None)):
                by_name.append(dev)
                if name_is_final:
                    fut.set_result(dev)

        factory = self._scanner_factory or _bleak().BleakScanner
        # leaving the scanner context stops discovery -> frees the radio
        async with factory(detection_callback=cb):
            try:
                return await asyncio.wait_for(asyncio.shield(fut), timeout)
            except asyncio.TimeoutError:
                return by_name[0] if by_name else None

    def drop_bond(self, address):
        self._admin.drop_bond(address)

    def reset_adapter(self, address):
        self._admin.reset_adapter(address)


class BleakAdvertScanner:
    """Scanner: one timed BleakScanner.discover() pass, as plain Adverts."""

    def __init__(self, scanner_cls=None):
        self._scanner_cls = scanner_cls

    async def scan(self, timeout):
        cls = self._scanner_cls or _bleak().BleakScanner
        devices = await cls.discover(timeout=timeout, return_adv=True)
        return [Advert(address=addr, name=dev.name, rssi=adv.rssi,
                       service_uuids=list(adv.service_uuids or []))
                for addr, (dev, adv) in devices.items()]
