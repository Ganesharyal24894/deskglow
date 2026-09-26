"""drivers.ble_bleak: the bleak-backed LightLink and Scanner, with fake bleak."""
import pytest

from deskglow.drivers import ble_bleak
from deskglow.model.presets import get_preset

WRITE_UUID = get_preset().write_uuid
ADDR = "AA:BB:CC:DD:EE:FF"


class FakeClient:
    def __init__(self, target, timeout=None):
        self.target, self.timeout = target, timeout
        self.is_connected = False
        self.writes = []
        self.calls = []

    async def connect(self):
        self.calls.append("connect")
        self.is_connected = True

    async def disconnect(self):
        self.calls.append("disconnect")
        self.is_connected = False

    async def write_gatt_char(self, uuid, data, response=False):
        self.writes.append((uuid, bytes(data), response))


class Dev:
    def __init__(self, address, name="x"):
        self.address, self.name = address, name


def scanner_factory(devices, record):
    class FakeScanner:
        def __init__(self, detection_callback=None, **kw):
            self.cb = detection_callback

        async def __aenter__(self):
            record.append("enter")
            for d in devices:
                self.cb(d, None)
            return self

        async def __aexit__(self, *exc):
            record.append("exit")
            return False
    return FakeScanner


def make_link(devices=(), record=None):
    clients = []

    def client_factory(target, timeout=None):
        clients.append(FakeClient(target, timeout))
        return clients[-1]

    link = ble_bleak.BleakLink(WRITE_UUID, client_factory=client_factory,
                               scanner_factory=scanner_factory(list(devices), record
                                                               if record is not None else []))
    return link, clients


def test_preset_write_uuid_is_fff3():
    assert WRITE_UUID == "0000fff3-0000-1000-8000-00805f9b34fb"


async def test_session_writes_to_the_preset_characteristic_with_the_response_flag():
    """Every frame goes to the preset's write characteristic (fff3)."""
    link, clients = make_link()
    s = link.session(ADDR, 6.0)
    await s.write(b"\x7e" * 9, response=False)
    await s.write(b"\x01" * 9, response=True)
    assert clients[0].writes == [(WRITE_UUID, b"\x7e" * 9, False),
                                 (WRITE_UUID, b"\x01" * 9, True)]


async def test_session_delegates_connect_disconnect_and_state():
    link, clients = make_link()
    s = link.session(ADDR, 6.0)
    assert (clients[0].target, clients[0].timeout) == (ADDR, 6.0)
    assert s.is_connected is False
    await s.connect()
    assert s.is_connected is True
    await s.disconnect()
    assert s.is_connected is False
    assert clients[0].calls == ["connect", "disconnect"]


async def test_find_returns_only_the_matching_device_case_insensitively():
    record = []
    ours = Dev(ADDR.lower())
    link, _ = make_link([Dev("11:22:33:44:55:66"), ours], record)
    assert await link.find(ADDR, 1.0) is ours
    assert record == ["enter", "exit"]


async def test_find_returns_none_on_timeout_and_stops_scanning():
    """A missing strip must not leave discovery running (the speaker needs it)."""
    record = []
    link, _ = make_link([Dev("11:22:33:44:55:66")], record)
    assert await link.find(ADDR, 0.01) is None
    assert record == ["enter", "exit"]


def test_bond_and_adapter_housekeeping_is_delegated():
    calls = []

    class Admin:
        def drop_bond(self, a):
            calls.append(("drop", a))

        def reset_adapter(self, a):
            calls.append(("reset", a))

    link = ble_bleak.BleakLink(WRITE_UUID, admin=Admin())
    link.drop_bond(ADDR)
    link.reset_adapter(None)
    assert calls == [("drop", ADDR), ("reset", None)]


class Adv:
    def __init__(self, uuids, rssi):
        self.service_uuids, self.rssi = uuids, rssi


async def test_scanner_converts_discover_results_into_adverts():
    seen = {}

    class FakeScanner:
        @staticmethod
        async def discover(timeout=10.0, return_adv=False):
            seen.update(timeout=timeout, return_adv=return_adv)
            return {"A": (Dev("A", "MELK"), Adv(["u1"], -40)),
                    "B": (Dev("B", None), Adv(None, None))}

    got = await ble_bleak.BleakAdvertScanner(scanner_cls=FakeScanner).scan(3.0)
    assert seen == {"timeout": 3.0, "return_adv": True}
    assert [(a.address, a.name, a.rssi, a.service_uuids) for a in got] == [
        ("A", "MELK", -40, ["u1"]), ("B", None, None, [])]


@pytest.mark.parametrize("attr", ["session", "find", "drop_bond", "reset_adapter"])
def test_bleak_link_implements_the_light_link_interface(attr):
    from deskglow.services.link import LightLink
    assert hasattr(LightLink, attr) and callable(getattr(ble_bleak.BleakLink, attr))
