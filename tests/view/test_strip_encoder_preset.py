"""The strip encoder renders from the controller preset, not from constants."""
import dataclasses

import pytest

from deskglow.model.presets import get_preset
from deskglow.view.strip import StripEncoder


@pytest.fixture
def custom():
    """A made-up controller: different framing, byte order and ranges."""
    base = get_preset()
    frames = {
        "power_on": (0xAA, 0x01),
        "power_off": (0xAA, 0x02),
        "color": (0xAA, 0x10, "b", "g", "r", 0x55),
        "brightness": (0xAA, 0x20, "brightness"),
        "effect": (0xAA, 0x30, "effect"),
        "speed": (0xAA, 0x40, "speed"),
        "status_query": (0xAA, 0xFF),
    }
    ranges = {"r": (0, 200), "g": (10, 255), "b": (0, 255),
              "brightness": (0, 31), "speed": (1, 20), "effect": (0x40, 0x60)}
    return dataclasses.replace(base, frames=frames, ranges=ranges)


def test_default_encoder_uses_the_default_preset():
    assert StripEncoder().preset == get_preset()


def test_every_command_comes_from_the_preset_templates(custom):
    enc = StripEncoder(custom)
    assert enc.power(True) == bytes([0xAA, 0x01])
    assert enc.power(False) == bytes([0xAA, 0x02])
    assert enc.color(1, 20, 3) == bytes([0xAA, 0x10, 3, 20, 1, 0x55])
    assert enc.brightness(7) == bytes([0xAA, 0x20, 7])
    assert enc.effect(0x50) == bytes([0xAA, 0x30, 0x50])
    assert enc.speed(5) == bytes([0xAA, 0x40, 5])
    assert enc.status_query() == bytes([0xAA, 0xFF])


@pytest.mark.parametrize("call,expected", [
    (lambda e: e.color(255, 0, 300), bytes([0xAA, 0x10, 255, 10, 200, 0x55])),
    (lambda e: e.brightness(100), bytes([0xAA, 0x20, 31])),
    (lambda e: e.speed(0), bytes([0xAA, 0x40, 1])),
    (lambda e: e.effect(0), bytes([0xAA, 0x30, 0x40])),
    (lambda e: e.effect(0xFF), bytes([0xAA, 0x30, 0x60])),
])
def test_each_placeholder_is_clamped_to_its_preset_range(custom, call, expected):
    assert call(StripEncoder(custom)) == expected


def test_render_fills_named_placeholders_directly(custom):
    enc = StripEncoder(custom)
    assert enc.render("brightness", brightness=12.9) == bytes([0xAA, 0x20, 12])
    assert enc.render("power_on") == bytes([0xAA, 0x01])


def test_render_needs_a_value_for_every_placeholder(custom):
    with pytest.raises(KeyError):
        StripEncoder(custom).render("color", r=1, g=2)
