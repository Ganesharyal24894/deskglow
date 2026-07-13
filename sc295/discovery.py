"""Discover ELK-BLEDOM / MELK style BLE LED strips on any machine.

Filters scan results to likely LED controllers so `setup` can auto-find the
strip without the user knowing its MAC address.
"""
import asyncio

from bleak import BleakScanner

# the service all these controllers advertise
FFF0_SERVICE = "0000fff0-0000-1000-8000-00805f9b34fb"
# name prefixes commonly used by these controllers
NAME_HINTS = ("MELK", "ELK", "LEDBLE", "LED-BLE", "LEDBle", "BLEDOM",
              "LED", "SP", "KS", "iDeal", "Triones", "QHM")


def _looks_like_strip(name, adv):
    svcs = [s.lower() for s in (adv.service_uuids or [])]
    if FFF0_SERVICE in svcs:
        return True
    if name:
        up = name.upper()
        return any(h.upper() in up for h in NAME_HINTS)
    return False


async def scan_candidates(timeout=10.0):
    """Return a list of likely LED strips: dicts with address/name/rssi/certain,
    strongest signal first. `certain` is True when it advertises the fff0 service.
    """
    found = {}
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for addr, (dev, adv) in devices.items():
        name = dev.name or ""
        if _looks_like_strip(name, adv):
            certain = FFF0_SERVICE in [s.lower() for s in (adv.service_uuids or [])]
            found[addr] = {"address": addr, "name": name or "(unknown)",
                           "rssi": adv.rssi, "certain": certain}
    return sorted(found.values(), key=lambda d: (not d["certain"], -d["rssi"]))


def scan_candidates_sync(timeout=10.0):
    return asyncio.run(scan_candidates(timeout))
