"""Patterns mode takes its effect table from the controller preset it is given,
and renders frames through the context's encoder (never a hard-coded protocol)."""
import dataclasses

import pytest
from fakes import make_services
from mode_clock import drive, install

from deskglow.controller import modes
from deskglow.controller.modes import patterns as pat_mod
from deskglow.controller.modes.patterns import Patterns, pattern_names
from deskglow.model.presets import get_preset

OTHER = dataclasses.replace(get_preset(), effects={"glow": 0x05, "zap": 0x09},
                            default_effect="zap")


@pytest.fixture
def instant(monkeypatch):
    return install(monkeypatch, pat_mod)


def test_a_given_preset_supplies_the_effect_ids():
    m = Patterns("glow", 10, preset=OTHER)
    assert (m.pattern, m.effect_id) == ("glow", 0x05)


@pytest.mark.parametrize("name", ["fade-colors", "nope", None])
def test_unknown_names_fall_back_to_the_given_presets_default(name):
    """A name from another controller's table is unknown to this one."""
    m = Patterns(name, 10, preset=OTHER)
    assert (m.pattern, m.effect_id) == ("zap", 0x09)


def test_build_passes_the_preset_through():
    assert modes.build("pattern", {"name": "glow"}, preset=OTHER).effect_id == 0x05
    assert modes.build("pattern", {}, preset=OTHER).pattern == "zap"


def test_build_without_a_preset_uses_the_default_table():
    assert modes.build("pattern", {}).pattern == get_preset().default_effect


def test_pattern_names_follow_the_given_preset():
    assert pattern_names(OTHER) == ["glow", "zap"]
    assert pattern_names() == get_preset().effect_names()


class RecordingEncoder:
    """A FrameEncoder that tags every frame, to prove which encoder was used."""

    def __init__(self):
        self.calls = []

    def _frame(self, *call):
        self.calls.append(call)
        return repr(call).encode()

    def brightness(self, pct):
        return self._frame("brightness", pct)

    def effect(self, effect_id):
        return self._frame("effect", effect_id)

    def speed(self, pct):
        return self._frame("speed", pct)


async def test_frames_are_rendered_by_the_context_encoder(make_ctx, instant):
    enc = RecordingEncoder()
    ctx = make_ctx(state={"max_brightness": 70}, services=make_services(encoder=enc))
    await drive(Patterns("glow", 33, preset=OTHER), ctx,
                lambda c: len(c.device.frames) >= 3)
    assert enc.calls[:3] == [("brightness", 70), ("effect", 0x05), ("speed", 33)]
    assert ctx.device.frames[:3] == [repr(c).encode() for c in enc.calls[:3]]
