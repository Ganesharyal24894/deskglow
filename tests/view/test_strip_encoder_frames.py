"""Byte-for-byte tests for the strip encoder: exact frames.

These frames are the device contract: the strip silently ignores anything it
does not recognise, so a regression here is invisible until someone plugs in a
real strip. Every frame is pinned to the literal bytes the pre-preset
protocol.py produced, proving the preset-driven encoder is byte-identical.
"""
import pytest

from deskglow.model.presets import get_preset
from deskglow.view.strip import StripEncoder

protocol = StripEncoder()   # the default (ELK-BLEDOM) preset


# ------------------------------------------------------------ constants -----

def test_characteristic_uuids():
    """Writes go to fff3, notifications come back on fff4."""
    assert get_preset().write_uuid == "0000fff3-0000-1000-8000-00805f9b34fb"
    assert get_preset().notify_uuid == "0000fff4-0000-1000-8000-00805f9b34fb"


# -------------------------------------------------------- exact frames ------

def test_power_on_frame():
    """Power on: 7E 00 04 F0 00 01 FF 00 EF."""
    assert protocol.power(True) == bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])


def test_power_off_frame():
    """Power off: 7E 00 04 00 00 00 FF 00 EF."""
    assert protocol.power(False) == bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])


def test_power_on_and_off_differ():
    """The on/off frames must not collapse into each other."""
    assert protocol.power(True) != protocol.power(False)


@pytest.mark.parametrize("truthy", [True, 1, "yes", [0]])
def test_power_accepts_truthy_values(truthy):
    """Any truthy argument means 'on'."""
    assert protocol.power(truthy) == protocol.power(True)


@pytest.mark.parametrize("falsy", [False, 0, "", None, []])
def test_power_accepts_falsy_values(falsy):
    """Any falsy argument means 'off'."""
    assert protocol.power(falsy) == protocol.power(False)


@pytest.mark.parametrize("rgb,expected", [
    ((0, 0, 0), [0x7E, 0x00, 0x05, 0x03, 0x00, 0x00, 0x00, 0x00, 0xEF]),
    ((255, 255, 255), [0x7E, 0x00, 0x05, 0x03, 0xFF, 0xFF, 0xFF, 0x00, 0xEF]),
    ((1, 2, 3), [0x7E, 0x00, 0x05, 0x03, 0x01, 0x02, 0x03, 0x00, 0xEF]),
    ((255, 136, 0), [0x7E, 0x00, 0x05, 0x03, 0xFF, 0x88, 0x00, 0x00, 0xEF]),
])
def test_color_frame(rgb, expected):
    """Colour: 7E 00 05 03 <R> <G> <B> 00 EF."""
    assert protocol.color(*rgb) == bytes(expected)


def test_color_channel_order_is_r_g_b():
    """Bytes 4/5/6 are red, green and blue in that order -- not BGR."""
    frame = protocol.color(0x11, 0x22, 0x33)
    assert frame[4] == 0x11
    assert frame[5] == 0x22
    assert frame[6] == 0x33
    assert protocol.color(255, 0, 0)[4:7] == bytes([255, 0, 0])
    assert protocol.color(0, 255, 0)[4:7] == bytes([0, 255, 0])
    assert protocol.color(0, 0, 255)[4:7] == bytes([0, 0, 255])


@pytest.mark.parametrize("pct,byte", [(0, 0x00), (1, 0x01), (50, 0x32), (100, 0x64)])
def test_brightness_frame(pct, byte):
    """Brightness: 7E 00 01 <0..100> 00 00 00 00 EF."""
    assert protocol.brightness(pct) == bytes([0x7E, 0x00, 0x01, byte, 0x00, 0x00, 0x00, 0x00, 0xEF])


@pytest.mark.parametrize("eid", [0x00, 0x01, 0x25, 0x80, 0xFF])
def test_effect_frame(eid):
    """Effect: 7E 00 03 <id> 03 00 00 00 EF."""
    assert protocol.effect(eid) == bytes([0x7E, 0x00, 0x03, eid, 0x03, 0x00, 0x00, 0x00, 0xEF])


@pytest.mark.parametrize("pct,byte", [(0, 0x00), (25, 0x19), (100, 0x64)])
def test_speed_frame(pct, byte):
    """Speed: 7E 00 02 <0..100> 00 00 00 00 EF."""
    assert protocol.speed(pct) == bytes([0x7E, 0x00, 0x02, byte, 0x00, 0x00, 0x00, 0x00, 0xEF])


def test_status_query_frame():
    """Status query: an all-zero payload, 7E 00 00 00 00 00 00 00 EF."""
    assert protocol.status_query() == bytes([0x7E, 0x00, 0x00, 0x00, 0x00,
                                             0x00, 0x00, 0x00, 0xEF])


def test_command_bytes_are_distinct():
    """Byte 2 is the command id and each builder must use its own."""
    ids = {
        "brightness": protocol.brightness(50)[2],
        "speed": protocol.speed(50)[2],
        "effect": protocol.effect(1)[2],
        "power": protocol.power(True)[2],
        "color": protocol.color(1, 2, 3)[2],
        "status": protocol.status_query()[2],
    }
    assert ids == {"status": 0x00, "brightness": 0x01, "speed": 0x02,
                   "effect": 0x03, "power": 0x04, "color": 0x05}
    assert len(set(ids.values())) == len(ids)
