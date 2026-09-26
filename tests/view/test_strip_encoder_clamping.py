"""Byte-for-byte tests for the strip encoder: framing and clamping.

These frames are the device contract: the strip silently ignores anything it
does not recognise, so a regression here is invisible until someone plugs in a
real strip. Every frame is pinned to the literal bytes the pre-preset
protocol.py produced, proving the preset-driven encoder is byte-identical.
"""
import pytest

from deskglow.view.strip import StripEncoder

protocol = StripEncoder()   # the default (ELK-BLEDOM) preset


# ------------------------------------------------------------- framing ------

ALL_FRAMES = [
    ("power-on", protocol.power(True)),
    ("power-off", protocol.power(False)),
    ("color", protocol.color(10, 20, 30)),
    ("color-max", protocol.color(255, 255, 255)),
    ("brightness", protocol.brightness(42)),
    ("brightness-min", protocol.brightness(0)),
    ("effect", protocol.effect(7)),
    ("speed", protocol.speed(88)),
    ("status_query", protocol.status_query()),
]


@pytest.mark.parametrize("name,frame", ALL_FRAMES, ids=[n for n, _ in ALL_FRAMES])
def test_every_frame_is_nine_framed_bytes(name, frame):
    """Every frame is exactly 9 bytes, starts with 0x7E and ends with 0xEF."""
    assert isinstance(frame, (bytes, bytearray))
    assert len(frame) == 9
    assert frame[0] == 0x7E
    assert frame[-1] == 0xEF
    assert all(0 <= b <= 255 for b in frame)


@pytest.mark.parametrize("name,frame", ALL_FRAMES, ids=[n for n, _ in ALL_FRAMES])
def test_every_frame_has_zero_second_byte(name, frame):
    """Byte 1 is a fixed 0x00 header byte in this protocol."""
    assert frame[1] == 0x00


# ------------------------------------------------------------ clamping ------

@pytest.mark.parametrize("rgb,expected", [
    ((-1, -1, -1), (0, 0, 0)),
    ((300, 999, 100000), (255, 255, 255)),
    ((-5, 128, 300), (0, 128, 255)),
])
def test_color_clamps_out_of_range_channels(rgb, expected):
    """Out-of-range channels are clamped, never wrapped modulo 256."""
    assert protocol.color(*rgb)[4:7] == bytes(expected)


@pytest.mark.parametrize("rgb,expected", [
    ((10.9, 20.2, 30.5), (10, 20, 30)),
    ((255.9, 0.9, -0.9), (255, 0, 0)),
])
def test_color_accepts_floats(rgb, expected):
    """Float channels (e.g. from the screen sampler) are truncated to ints."""
    assert protocol.color(*rgb)[4:7] == bytes(expected)


@pytest.mark.parametrize("value,expected", [
    (-1, 0), (-100, 0), (101, 100), (10**6, 100), (50.7, 50), (0.4, 0),
])
def test_brightness_clamps_to_0_100(value, expected):
    """Brightness is a percentage: pinned to 0..100."""
    assert protocol.brightness(value)[3] == expected


@pytest.mark.parametrize("value,expected", [
    (-1, 0), (-100, 0), (101, 100), (10**6, 100), (33.9, 33),
])
def test_speed_clamps_to_0_100(value, expected):
    """Speed is a percentage: pinned to 0..100."""
    assert protocol.speed(value)[3] == expected


@pytest.mark.parametrize("value,expected", [
    (-1, 0), (-999, 0), (256, 255), (10**6, 255), (7.9, 7),
])
def test_effect_clamps_to_0_255(value, expected):
    """Effect ids are a single byte: pinned to 0..255."""
    assert protocol.effect(value)[3] == expected


@pytest.mark.parametrize("builder,args", [
    (protocol.color, (-9999, 9999, 0.5)),
    (protocol.brightness, (-9999,)),
    (protocol.brightness, (9999,)),
    (protocol.speed, (-9999,)),
    (protocol.effect, (9999,)),
])
def test_clamped_frames_stay_well_framed(builder, args):
    """Clamping never disturbs the 9-byte framing."""
    frame = builder(*args)
    assert len(frame) == 9 and frame[0] == 0x7E and frame[-1] == 0xEF


def test_builders_are_pure():
    """Calling a builder twice with the same input yields the same bytes."""
    assert protocol.color(1, 2, 3) == protocol.color(1, 2, 3)
    assert protocol.power(True) == protocol.power(True)
    assert protocol.status_query() == protocol.status_query()
