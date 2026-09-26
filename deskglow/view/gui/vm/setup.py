"""First-run Setup: scan results as rows, the headline, manual address entry."""
from dataclasses import dataclass

from ....model import settings_rules

SIGNAL = ((-60, 4, "Strong"), (-70, 3, "Good"), (-80, 2, "Fair"))


@dataclass(frozen=True)
class Row:
    name: str
    address: str
    rssi: object
    level: int          # 0-4 lit signal bars
    signal_text: str
    likely: bool


def signal(rssi):
    """(bars 0-4, word) for an RSSI in dBm."""
    if not isinstance(rssi, (int, float)):
        return 0, "Unknown"
    for floor, bars, word in SIGNAL:
        if rssi >= floor:
            return bars, word
    return 1, "Weak"


def rows(candidates):
    """Rows in the daemon's ranking. "Most likely" marks the first when it
    advertises the controller's service (or is the only one found)."""
    out = []
    for i, c in enumerate(candidates):
        level, text = signal(c.get("rssi"))
        likely = i == 0 and (bool(c.get("certain")) or len(candidates) == 1)
        out.append(Row(c.get("name") or "(unknown)", c.get("address", ""), c.get("rssi"),
                       level, text, likely))
    return out


def headline(scanning, count, error=None):
    if scanning:
        return "Scanning…"
    if error:
        return f"Scan failed: {error}"
    if count == 0:
        return "No LED controllers found"
    return f"Found {count} LED controller{'s' if count != 1 else ''}"


def manual_address(text):
    """The normalised address typed by hand, or None if it isn't one."""
    try:
        return settings_rules.address(text)
    except ValueError:
        return None


def scan_request():
    return {"cmd": "scan", "timeout": 8}


def use_request(row=None, manual=None):
    """set_address for the chosen row, or for a hand-typed address."""
    if manual is not None:
        return {"cmd": "set_address", "address": manual}
    req = {"cmd": "set_address", "address": row.address, "name": row.name}
    if isinstance(row.rssi, int):
        req["rssi"] = row.rssi
    return req
