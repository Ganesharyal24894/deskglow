"""The light palette: complete, well-formed, the design's values, and accent_ink."""
import dataclasses
import re

import pytest

from deskglow.view.gui import accent, theme
from deskglow.view.gui.widgets.base import token

HEX = re.compile(r"^#[0-9A-F]{6}$")
FIELDS = [f.name for f in dataclasses.fields(theme.Palette)]


@pytest.mark.parametrize("name", FIELDS)
def test_light_defines_every_token_dark_does(name):
    dark, light = getattr(theme.DARK, name), getattr(theme.LIGHT, name)
    assert type(light) is type(dark), name
    if isinstance(dark, str) and name != "name":
        for value in (dark, light):
            assert HEX.match(value) or value in FIELDS + ["accent", "accent_ink"], (name, value)


@pytest.mark.parametrize("name", [n for n in FIELDS if n != "name"])
def test_every_token_resolves_to_a_colour_in_both_palettes(name):
    for palette in (theme.DARK, theme.LIGHT):
        theme.set_current(palette)
        value = getattr(palette, name)
        if isinstance(value, str):
            assert HEX.match(token(name).upper()), (palette.name, name)


def test_light_uses_the_design_values():
    p = theme.LIGHT
    assert (p.bg, p.side, p.card, p.card_border, p.control_border) == (
        "#F4F3EF", "#EFEEEA", "#FFFFFF", "#E4E2DC", "#D6D4CD")
    assert (p.inset, p.filter_well, p.monitor, p.tile, p.raised) == (
        "#F2F1ED", "#ECEBE6", "#FFFFFF", "#F8F7F4", "#F2F1ED")
    assert (p.stage, p.stage_text, p.stage_muted) == ("#1B1B20", "#F2F2F5", "#B4B4C0")
    assert (p.focus_label, p.focus_primary, p.focus_on_accent, p.ring_track) == (
        "#15708F", "#1C7FA3", "#FFFFFF", "#ECEAE5")
    assert (p.badge_bg, p.badge_text, p.bar_off) == ("#FBEBDD", "#7A5230", "#D6D4CD")
    assert (p.fx_white, p.fx_dark, p.blink_gap, p.preview_glow_alpha) == (
        "#CFCFD6", "#E9E8E4", "#E9E8E4", 0.0)
    assert (p.knob_on, p.seg_shadow, p.card_shadow, p.ink_scale) == ("#FFFFFF", 0.12, 0.08, 0.55)


def test_ink_matches_the_design_rounding():
    assert theme.ink("#FFB46E", 0.55) == "#8C633D"
    assert theme.ink("#1E4696", 0.55) == "#112753"       # 16.5, 38.5, 82.5 round up (JS)
    assert theme.ink("#28A0C8", 1.0) == "#28A0C8"


def test_strokes_use_ink_and_fills_the_true_accent_in_light():
    accent.set_accent("#FFB46E")
    theme.set_current(theme.LIGHT)
    assert token("accent_ink") == "#8C633D" and token("accent") == "#FFB46E"
    assert token("primary_border") == "#8C633D"       # primary buttons get an ink border
    theme.set_current(theme.DARK)
    assert token("primary_border") == token("accent_ink") == "#FFB46E"
    assert token("badge_text") == "#FFB46E"
