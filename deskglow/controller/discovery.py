"""Discover likely LED strips among nearby BLE advertisements.

Filters scan results to controllers a preset recognises (by advertised service,
else by name hint) so `setup` can auto-find the strip without the user knowing
its MAC address.
"""
from ..model.presets import get_preset

UNKNOWN_NAME = "(unknown)"   # shown for a strip that advertises no name


def looks_like_strip(name, service_uuids, preset=None):
    """True if an advertisement plausibly comes from a `preset` controller."""
    preset = preset or get_preset()
    if is_certain(service_uuids, preset):
        return True
    if name:
        up = name.upper()
        return any(h.upper() in up for h in preset.name_hints)
    return False


def is_certain(service_uuids, preset=None):
    """True when the device advertises one of the preset's service UUIDs."""
    preset = preset or get_preset()
    svcs = [s.lower() for s in (service_uuids or [])]
    return any(u in svcs for u in preset.service_uuids)


def _rank(d):
    # Some adapters report no RSSI at all; those devices sort last instead of
    # raising a TypeError that would sink the whole scan.
    rssi = d["rssi"]
    return (not d["certain"], -rssi if rssi is not None else float("inf"))


def candidates(adverts, preset=None):
    """Likely strips from a list of Adverts: dicts with address/name/rssi/certain,
    strongest signal first. `certain` means it advertises the preset's service."""
    found = {}
    for adv in adverts:
        name = adv.name or ""
        if looks_like_strip(name, adv.service_uuids, preset):
            found[adv.address] = {"address": adv.address, "name": name or UNKNOWN_NAME,
                                  "rssi": adv.rssi,
                                  "certain": is_certain(adv.service_uuids, preset)}
    return sorted(found.values(), key=_rank)


async def scan_candidates(scanner, timeout=10.0, preset=None):
    """Scan with `scanner` for `timeout` seconds and return candidates()."""
    return candidates(await scanner.scan(timeout), preset)
