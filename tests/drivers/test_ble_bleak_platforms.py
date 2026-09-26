"""ble_bleak on macOS/Windows: saved-name fallback for per-Mac CoreBluetooth
addresses, and adapter housekeeping where the OS owns it."""
import asyncio
import types

import pytest

from deskglow.drivers import ble_bleak
from deskglow.services.link import AdapterError

UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
SAVED_UUID = "4A1C1F7E-0000-4000-8000-00000000AAAA"


class Dev:
    def __init__(self, address, name):
        self.address, self.name = address, name


def scanner(devices, delay=0.0):
    class FakeScanner:
        def __init__(self, detection_callback=None, **kw):
            self.cb = detection_callback

        async def __aenter__(self):
            async def feed():
                for d in devices:
                    await asyncio.sleep(delay)
                    self.cb(d, types.SimpleNamespace(local_name=d.name))
            self.task = asyncio.ensure_future(feed())
            return self

        async def __aexit__(self, *exc):
            self.task.cancel()
            return False
    return FakeScanner


def link(devices, name="ELK-BLEDOM", delay=0.0):
    return ble_bleak.BleakLink(UUID, scanner_factory=scanner(devices, delay),
                               admin=ble_bleak.NoAdapterAdmin(), saved_name=lambda: name)


async def test_the_exact_address_still_wins_over_a_name_match():
    here = Dev(SAVED_UUID, "ELK-BLEDOM")
    other = Dev("11111111-2222-3333-4444-555555555555", "ELK-BLEDOM")
    assert await link([other, here]).find(SAVED_UUID, 1.0) is here


async def test_a_foreign_uuid_falls_back_to_the_saved_name_after_the_scan():
    """The config came from another Mac: its UUID never appears here."""
    strip = Dev("99999999-0000-4000-8000-000000000001", "ELK-BLEDOM")
    phone = Dev("88888888-0000-4000-8000-000000000001", "iPhone")
    assert await link([phone, strip]).find(SAVED_UUID, 0.2) is strip


async def test_a_linux_mac_address_on_macos_uses_the_name_immediately():
    strip = Dev("99999999-0000-4000-8000-000000000001", "ELK-BLEDOM")
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    assert await link([strip]).find("AA:BB:CC:DD:EE:FF", 5.0) is strip
    assert loop.time() - t0 < 1.0, "waited out the timeout for a MAC CoreBluetooth never shows"


@pytest.mark.parametrize("name", [None, ""])
async def test_without_a_saved_name_a_missing_address_is_not_found(name):
    strip = Dev("99999999-0000-4000-8000-000000000001", "ELK-BLEDOM")
    assert await link([strip], name=name).find(SAVED_UUID, 0.2) is None


async def test_a_broken_name_lookup_is_treated_as_no_name():
    def boom():
        raise OSError("config unreadable")
    lk = ble_bleak.BleakLink(UUID, scanner_factory=scanner([Dev("X", "ELK-BLEDOM")]),
                             saved_name=boom)
    assert await lk.find(SAVED_UUID, 0.1) is None


async def test_no_fallback_is_configured_on_linux_by_default():
    lk = ble_bleak.BleakLink(UUID, scanner_factory=scanner([Dev("X", "ELK-BLEDOM")]))
    assert await lk.find("AA:BB:CC:DD:EE:FF", 0.1) is None


def test_os_owned_adapters_forget_nothing_and_explain_reset():
    lk = link([])
    lk.drop_bond("AA:BB:CC:DD:EE:FF")          # nothing to do, never raises
    with pytest.raises(AdapterError, match="Turn Bluetooth off and on"):
        lk.reset_adapter("AA:BB:CC:DD:EE:FF")
