"""deskglow.controller.discovery: which advertisements look like an LED strip,
and how scan results are shaped and ordered. The scanner is always a fake."""
import pytest
from fakes import FakeScanner

from deskglow.controller import discovery
from deskglow.model.presets import get_preset
from deskglow.services.scanner import Advert

FFF0 = "0000fff0-0000-1000-8000-00805f9b34fb"
BATTERY = "0000180f-0000-1000-8000-00805f9b34fb"


def adv(address, name, service_uuids=None, rssi=-60):
    return Advert(address=address, name=name, rssi=rssi, service_uuids=service_uuids or [])


# -------------------------------------------------------- looks_like_strip ---

def test_the_match_service_comes_from_the_preset():
    assert get_preset().service_uuids == (FFF0,)


@pytest.mark.parametrize("uuid", [
    FFF0, FFF0.upper(), "0000FFF0-0000-1000-8000-00805F9B34FB",
    "0000fFf0-0000-1000-8000-00805f9b34fb",
])
def test_fff0_service_matches_regardless_of_case(uuid):
    """BlueZ reports UUIDs in whatever case it likes; matching must not care."""
    assert discovery.looks_like_strip("whatever", [uuid]) is True
    assert discovery.is_certain([uuid]) is True


@pytest.mark.parametrize("name", [
    "MELK-OA10", "melk-oa10", "ELK-BLEDOM", "LEDBLE-1234", "LED-BLE-99",
    "BLEDOM", "Triones-A1", "QHM-12", "SP110E", "KS03", "iDeal-LED",
])
def test_known_name_prefixes_match(name):
    """The usual ELK/MELK-family controller names are recognised by name alone."""
    assert discovery.looks_like_strip(name, []) is True
    assert discovery.is_certain([]) is False


@pytest.mark.parametrize("name", ["Bose QC35", "iPhone", "Galaxy Watch4", "MX Master 3"])
def test_unrelated_devices_are_rejected(name):
    """Headphones, phones and mice must never be offered as an LED strip."""
    assert discovery.looks_like_strip(name, [BATTERY]) is False


@pytest.mark.parametrize("name", [None, ""])
def test_missing_name_without_the_service_is_not_a_strip(name):
    """A nameless beacon with no fff0 service is just noise."""
    assert discovery.looks_like_strip(name, []) is False


@pytest.mark.parametrize("name", [None, ""])
def test_missing_name_with_the_service_is_still_a_strip(name):
    """Plenty of these controllers advertise fff0 before they advertise a name."""
    assert discovery.looks_like_strip(name, [FFF0]) is True


def test_none_service_uuid_list_does_not_crash():
    """Some adapters report service_uuids=None; that must not raise."""
    assert discovery.looks_like_strip(None, None) is False
    assert discovery.looks_like_strip("MELK-OA10", None) is True


# ---------------------------------------------------------- scan_candidates --

async def test_scan_candidates_shape():
    """Each candidate is a flat dict the CLI can print directly."""
    scanner = FakeScanner([adv("AA:BB:CC:DD:EE:FF", "MELK-OA10", [FFF0], rssi=-42)])
    got = await discovery.scan_candidates(scanner, timeout=3.0)
    assert got == [{"address": "AA:BB:CC:DD:EE:FF", "name": "MELK-OA10",
                    "rssi": -42, "certain": True}]
    assert scanner.timeouts == [3.0]


async def test_scan_candidates_default_timeout_is_ten_seconds():
    scanner = FakeScanner([])
    await discovery.scan_candidates(scanner)
    assert scanner.timeouts == [10.0]


async def test_nameless_strip_is_labelled_unknown():
    """A strip that advertises fff0 but no name still needs something printable."""
    got = await discovery.scan_candidates(FakeScanner([adv("AA:11:22:33:44:55", None, [FFF0])]))
    assert got[0]["name"] == "(unknown)"
    assert got[0]["certain"] is True


async def test_unrelated_devices_are_excluded():
    """Only likely strips are returned — everything else is filtered out."""
    got = await discovery.scan_candidates(FakeScanner([
        adv("AA:00:00:00:00:01", "MELK-OA10", [FFF0]),
        adv("BB:00:00:00:00:02", "Bose QC35"),
        adv("CC:00:00:00:00:03", None),
        adv("DD:00:00:00:00:04", ""),
    ]))
    assert [c["address"] for c in got] == ["AA:00:00:00:00:01"]


async def test_fff0_devices_sort_before_name_only_matches():
    """A confirmed fff0 controller outranks a weak name guess, even a louder one."""
    got = await discovery.scan_candidates(FakeScanner([
        adv("BB:00:00:00:00:02", "LEDBLE-loud", [], rssi=-30),
        adv("AA:00:00:00:00:01", "MELK-quiet", [FFF0], rssi=-90),
    ]))
    assert [c["address"] for c in got] == ["AA:00:00:00:00:01", "BB:00:00:00:00:02"]
    assert [c["certain"] for c in got] == [True, False]


async def test_stronger_signal_sorts_first_within_a_group():
    """Within equally-certain devices, the nearest strip is offered first."""
    got = await discovery.scan_candidates(FakeScanner([
        adv("AA:00:00:00:00:01", "MELK-far", [FFF0], rssi=-88),
        adv("BB:00:00:00:00:02", "MELK-near", [FFF0], rssi=-35),
        adv("CC:00:00:00:00:03", "MELK-mid", [FFF0], rssi=-60),
        adv("DD:00:00:00:00:04", "LEDBLE-near", [], rssi=-31),
        adv("EE:00:00:00:00:05", "LEDBLE-far", [], rssi=-77),
    ]))
    assert [c["name"] for c in got] == ["MELK-near", "MELK-mid", "MELK-far",
                                        "LEDBLE-near", "LEDBLE-far"]


async def test_empty_scan_returns_an_empty_list():
    """Nothing nearby is a normal outcome, not an error."""
    assert await discovery.scan_candidates(FakeScanner([])) == []


async def test_missing_rssi_does_not_break_the_scan():
    """An advertisement with no RSSI must be tolerated, not fatal to the whole scan."""
    got = await discovery.scan_candidates(FakeScanner([
        adv("AA:00:00:00:00:01", "MELK-OA10", [FFF0], rssi=None),
        adv("BB:00:00:00:00:02", "MELK-other", [FFF0], rssi=-40),
    ]))
    assert {c["address"] for c in got} == {"AA:00:00:00:00:01", "BB:00:00:00:00:02"}
    # the known-signal device should still be offered first
    assert got[0]["address"] == "BB:00:00:00:00:02"


def test_a_device_seen_twice_is_offered_once():
    got = discovery.candidates([adv("AA:00:00:00:00:01", "MELK", [FFF0], rssi=-80),
                                adv("AA:00:00:00:00:01", "MELK", [FFF0], rssi=-40)])
    assert len(got) == 1 and got[0]["rssi"] == -40
