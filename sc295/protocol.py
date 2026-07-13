"""ELK-BLEDOM wire protocol for the SC295 / MELK-OA10 strip.

All frames are 9 bytes, framed 0x7E .. 0xEF, written to characteristic fff3.
Confirmed empirically on this device (the Triones 0x56.. protocol does NOT work).
"""

WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def power(on):
    if on:
        return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])
    return bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])


def color(r, g, b):
    r = _clamp(r, 0, 255)
    g = _clamp(g, 0, 255)
    b = _clamp(b, 0, 255)
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def brightness(pct):
    p = _clamp(pct, 0, 100)
    return bytes([0x7E, 0x00, 0x01, p, 0x00, 0x00, 0x00, 0x00, 0xEF])


def effect(effect_id):
    e = _clamp(effect_id, 0, 255)
    return bytes([0x7E, 0x00, 0x03, e, 0x03, 0x00, 0x00, 0x00, 0xEF])


def speed(pct):
    p = _clamp(pct, 0, 100)
    return bytes([0x7E, 0x00, 0x02, p, 0x00, 0x00, 0x00, 0x00, 0xEF])


def status_query():
    # Some firmwares reply on fff4; harmless if ignored.
    return bytes([0x7E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xEF])
