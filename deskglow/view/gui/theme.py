"""Colour tokens for the desktop app. Every colour the app paints is defined
here, once, per palette; widgets ask `current()` at paint time.

Two accent tokens: "accent" (fills and glows: the strip's true colour) and
"accent_ink" (strokes and indicators: the accent darkened by the palette's
ink_scale, which a light palette needs for contrast; 1.0 on dark).

A token's value may name another token (e.g. primary_border = "accent_ink"),
resolved by widgets.base.token(). The Theme setting (System / Dark / Light)
resolves through `PALETTES`; see themer.ThemeSwitch for switching.
"""
import math
from dataclasses import dataclass

DEFAULT_ACCENT = "#FFB46E"


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str               # window background
    side: str             # sidebar background
    rule: str             # sidebar edge
    card: str             # card surface
    card_border: str
    raised: str           # raised buttons
    nav_active: str       # active nav item
    control_border: str   # outline of buttons, inputs, swatches; switch "off" track
    tile: str             # idle mode tile / scan row
    tile_active: str      # selected tile / chip / row
    monitor: str          # a screen in the Sync diagram
    inset: str            # wells inside cards (diagram, segmented, inputs)
    filter_well: str      # the Effects filter's well
    seg_on: str           # selected segment
    text: str
    strong: str           # emphasised text (active nav, selected segment)
    muted: str
    on_accent: str        # text on an accent-filled button
    primary_border: str   # outline of an accent-filled button
    ok: str               # connected dot
    warn: str             # connecting dot
    idle: str             # disconnected dot
    danger_border: str
    danger_text: str
    radio_off: str
    bar_off: str          # unlit signal bar
    badge_bg: str
    badge_text: str
    ring_track: str       # focus ring background track
    fx_dark: str          # dark stop in single-colour effect previews
    fx_white: str         # the "white" channel in effect previews
    blink_gap: str        # gaps in blink effect previews
    focus_label: str      # "FOCUS" over the timer
    focus_primary: str    # the Start/Pause button during the focus phase
    focus_on_accent: str  # text on that button
    swatch_ring: str      # selected swatch outline
    knob_on: str
    knob_off: str
    stage: str            # the strip preview's backdrop (stays dark in light mode)
    stage_line: str
    stage_text: str
    stage_muted: str
    stage_groove: str     # slider track on the stage
    strip_off: str        # the strip preview when the light is off
    preview_glow: str     # the faint halo around the Playing effect preview
    preview_glow_alpha: float
    seg_shadow: float     # alpha of the 0 1px 2px shadow under a selected segment
    nav_shadow: float     # ... under the active nav item
    card_shadow: float    # alpha of Setup's 0 12px 40px card shadow
    tray_pad: tuple       # (x, y) padding around the tray panel's strip
    ink_scale: float      # accent_ink = accent RGB x this (strokes/indicators)


DARK = Palette(
    name="dark", bg="#0F0F12", side="#0F0F12", rule="#22222A", card="#17171C",
    card_border="#25252D", raised="#1F1F26", nav_active="#1F1F26", control_border="#2A2A33",
    tile="#1C1C22", tile_active="#23232B", monitor="#1C1C22", inset="#111115",
    filter_well="#17171C", seg_on="#2A2A33", text="#ECECF1", strong="#FFFFFF", muted="#A0A0AD",
    on_accent="#141413", primary_border="accent", ok="#4ADE80", warn="#F5B84A", idle="#5A5A66",
    danger_border="#5A2A2A", danger_text="#FF8A80", radio_off="#4A4A55", bar_off="#34343D",
    badge_bg="#2B2419", badge_text="accent_ink", ring_track="#23232B", fx_dark="#1A1A1F",
    fx_white="#F2F2F2", blink_gap="#0F0F12", focus_label="#5CC6E8", focus_primary="#28A0C8",
    focus_on_accent="#0B1418", swatch_ring="#FFFFFF", knob_on="#141413", knob_off="#A0A0AD",
    stage="#17171C", stage_line="#25252D", stage_text="#ECECF1", stage_muted="#A0A0AD",
    stage_groove="#2A2A33", strip_off="#2A2A33", preview_glow="#FFFFFF",
    preview_glow_alpha=0.12, seg_shadow=0.0, nav_shadow=0.0, card_shadow=0.0, tray_pad=(4, 6),
    ink_scale=1.0,
)

LIGHT = Palette(
    name="light", bg="#F4F3EF", side="#EFEEEA", rule="#E2E0DA", card="#FFFFFF",
    card_border="#E4E2DC", raised="#F2F1ED", nav_active="#FFFFFF", control_border="#D6D4CD",
    tile="#F8F7F4", tile_active="#FFFFFF", monitor="#FFFFFF", inset="#F2F1ED",
    filter_well="#ECEBE6", seg_on="#FFFFFF", text="#1A1A1F", strong="#0E0E12", muted="#5E5E69",
    on_accent="#141413", primary_border="accent_ink", ok="#16A34A", warn="#B7791F",
    idle="#9A9AA5", danger_border="#F0C4BF", danger_text="#B3261E", radio_off="#A9A7A0",
    bar_off="#D6D4CD", badge_bg="#FBEBDD", badge_text="#7A5230", ring_track="#ECEAE5",
    fx_dark="#E9E8E4", fx_white="#CFCFD6", blink_gap="#E9E8E4", focus_label="#15708F",
    focus_primary="#1C7FA3", focus_on_accent="#FFFFFF", swatch_ring="#0E0E12",
    knob_on="#FFFFFF", knob_off="#FFFFFF", stage="#1B1B20", stage_line="#1B1B20",
    stage_text="#F2F2F5", stage_muted="#B4B4C0", stage_groove="#3A3A42", strip_off="#3A3A42",
    preview_glow="#FFFFFF", preview_glow_alpha=0.0, seg_shadow=0.12, nav_shadow=0.08,
    card_shadow=0.08, tray_pad=(16, 18), ink_scale=0.55,
)

# name -> Palette
PALETTES = {"dark": DARK, "light": LIGHT}
SHADOW = "#14141E"        # rgba(20,20,30,a) of the light theme's soft shadows


def ink(colour, scale):
    """`colour` (#RRGGBB) with every channel x `scale`, rounded like JS Math.round."""
    h = colour.lstrip("#")
    return "#" + "".join(f"{min(255, math.floor(int(h[i:i + 2], 16) * scale + 0.5)):02X}"
                         for i in (0, 2, 4))


def resolve(preference, system_dark=True):
    """The palette for a Theme setting ("system" | "dark" | "light").

    Falls back to dark for any palette that doesn't exist."""
    system = "dark" if system_dark else "light"
    wanted = preference if preference in ("dark", "light") else system
    return PALETTES.get(wanted, DARK)


_current = [DARK]


def current():
    return _current[0]


def set_current(palette):
    """Make `palette` the active one; True if that changed anything."""
    changed = _current[0] is not palette
    _current[0] = palette
    return changed
