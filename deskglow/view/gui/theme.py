"""Colour tokens for the desktop app. Every colour the app paints is defined
here, once, per palette; widgets ask `current()` at paint time.

Two accent tokens: "accent" (fills and glows: the strip's true colour) and
"accent_ink" (strokes and indicators: the accent darkened by the palette's
ink_scale, which a light palette needs for contrast; 1.0 on dark).

Only the dark palette exists so far. The Theme setting (System / Dark / Light)
resolves through `PALETTES`, so a light palette can be dropped in later by
registering it under "light"; until then Light (and System on a light desktop)
stays dark.
"""
from dataclasses import dataclass

DEFAULT_ACCENT = "#FFB46E"


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str               # window background
    rule: str             # sidebar edge
    card: str             # card surface
    card_border: str
    raised: str           # raised buttons, active nav item
    control_border: str   # outline of buttons, inputs, swatches
    tile: str             # idle mode tile
    tile_active: str      # selected tile / chip / row
    inset: str            # wells inside cards (diagram, segmented, inputs)
    seg_on: str           # selected segment
    text: str
    strong: str           # emphasised text (active nav, selected segment)
    muted: str
    on_accent: str        # text on an accent-filled button
    ok: str               # connected dot
    warn: str             # connecting dot
    idle: str             # disconnected dot
    danger_border: str
    danger_text: str
    radio_off: str
    bar_off: str          # unlit signal bar
    badge_bg: str
    ring_track: str       # focus ring background track
    fx_dark: str          # dark stop in single-colour effect previews
    blink_gap: str        # gaps in blink effect previews
    focus_label: str      # "FOCUS" over the timer
    focus_on_accent: str  # text on the cyan Pause button
    swatch_ring: str      # selected swatch outline
    knob_off: str
    preview_glow: str     # the faint halo around the Playing effect preview
    ink_scale: float      # accent_ink = accent RGB x this (strokes/indicators)


DARK = Palette(
    name="dark", bg="#0F0F12", rule="#22222A", card="#17171C", card_border="#25252D",
    raised="#1F1F26", control_border="#2A2A33", tile="#1C1C22", tile_active="#23232B",
    inset="#111115", seg_on="#2A2A33", text="#ECECF1", strong="#FFFFFF", muted="#A0A0AD",
    on_accent="#141413", ok="#4ADE80", warn="#F5B84A", idle="#5A5A66",
    danger_border="#5A2A2A", danger_text="#FF8A80", radio_off="#4A4A55", bar_off="#34343D",
    badge_bg="#2B2419", ring_track="#23232B", fx_dark="#1A1A1F", blink_gap="#0F0F12",
    focus_label="#5CC6E8", focus_on_accent="#0B1418", swatch_ring="#FFFFFF",
    knob_off="#A0A0AD", preview_glow="#FFFFFF", ink_scale=1.0,
)

# name -> Palette. Register a light palette here when one is designed.
PALETTES = {"dark": DARK}


def resolve(preference, system_dark=True):
    """The palette for a Theme setting ("system" | "dark" | "light").

    Falls back to dark for any palette that doesn't exist (yet)."""
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
