"""Circadian mode: colour temperature and brightness follow the time of day."""
import datetime as _dt
import types

import pytest
from mode_clock import drive, install

from deskglow.controller.modes import circadian as circ_mod
from deskglow.controller.modes.circadian import Circadian, _interp
from deskglow.model import color as colormod


@pytest.fixture
def instant(monkeypatch):
    return install(monkeypatch, circ_mod)


def _freeze_clock(monkeypatch, hour, minute=0):
    """Pin datetime.datetime.now() inside circadian.py to a fixed local time."""
    fixed = _dt.datetime(2026, 8, 22, hour, minute)

    class _FrozenDatetime:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr(circ_mod, "datetime",
                        types.SimpleNamespace(datetime=_FrozenDatetime))
    return fixed


# -------------------------------------------------------------- the mode ----

async def test_midday_is_cooler_and_brighter_than_late_evening(
        make_ctx, instant, monkeypatch):
    """The core promise: bluer/brighter at midday, redder/dimmer at night."""
    _freeze_clock(monkeypatch, 13)
    day_ctx = make_ctx()
    await drive(Circadian(), day_ctx, lambda c: len(c.device.colors) >= 30)
    day = day_ctx.device.colors[29]

    _freeze_clock(monkeypatch, 22)
    night_ctx = make_ctx()
    await drive(Circadian(), night_ctx, lambda c: len(c.device.colors) >= 30)
    night = night_ctx.device.colors[29]

    assert day[2] > night[2], "midday must be bluer in absolute terms"
    assert day[2] / max(day[0], 1) > night[2] / max(night[0], 1), \
        "midday must be relatively bluer (cooler) than late evening"
    assert sum(day) > sum(night), "late evening must be dimmer"
    assert night[0] > night[2], "late evening must be red-dominant (warm)"


@pytest.mark.parametrize("hour", list(range(24)))
async def test_mode_writes_valid_colours_at_every_hour(make_ctx, instant,
                                                       monkeypatch, hour):
    """Loop the whole clock: no hour may crash the mode or emit a bad colour."""
    _freeze_clock(monkeypatch, hour, 30)
    ctx = make_ctx()
    await drive(Circadian(), ctx, lambda c: len(c.device.colors) >= 30)
    assert ctx.device.colors
    for col in ctx.device.colors:
        assert len(col) == 3
        for c in col:
            assert isinstance(c, int) and 0 <= c <= 255
    assert max(ctx.device.colors[-1]) > 0, "the strip must never go dark"


async def test_target_colour_matches_the_interpolated_temperature(
        make_ctx, instant, monkeypatch):
    """The colour it eases toward is kelvin_to_rgb(interp) scaled by brightness."""
    _freeze_clock(monkeypatch, 17)
    ctx = make_ctx()
    await drive(Circadian(), ctx, lambda c: len(c.device.colors) >= 300)
    kelvin, bri = _interp(17.0)
    expected = colormod.scale(colormod.kelvin_to_rgb(kelvin), bri)
    got = ctx.device.colors[-1]
    assert max(abs(a - b) for a, b in zip(got, expected, strict=False)) <= 2


async def test_colour_eases_in_rather_than_snapping(make_ctx, instant, monkeypatch):
    """A smoother ramps toward the target so the change is never a hard cut."""
    _freeze_clock(monkeypatch, 12)
    ctx = make_ctx()
    await drive(Circadian(), ctx, lambda c: len(c.device.colors) >= 30)
    first, last = ctx.device.colors[0], ctx.device.colors[29]
    assert sum(first) < sum(last)
    for prev, cur in zip(ctx.device.colors[:30], ctx.device.colors[1:30], strict=False):
        assert all(c >= p for p, c in zip(prev, cur, strict=False))


async def test_logs_the_hour_temperature_and_brightness(make_ctx, instant, monkeypatch):
    """The log line is how a user checks the schedule is doing what they expect."""
    _freeze_clock(monkeypatch, 20, 30)
    ctx = make_ctx()
    await drive(Circadian(), ctx, lambda c: bool(c.logs))
    line = ctx.logs[0]
    assert "circadian" in line
    assert "20.5h" in line
    assert "K" in line


async def test_respects_the_brightness_ceiling(make_ctx, instant, monkeypatch):
    _freeze_clock(monkeypatch, 12)
    full = make_ctx()
    await drive(Circadian(), full, lambda c: len(c.device.colors) >= 300)
    capped = make_ctx(state={"max_brightness": 40})
    await drive(Circadian(), capped, lambda c: len(c.device.colors) >= 300)
    assert sum(capped.device.colors[-1]) < sum(full.device.colors[-1])
    for a, b in zip(capped.device.colors[-1], full.device.colors[-1], strict=False):
        assert a <= b * 0.4 + 1


async def test_re_evaluates_the_time_periodically(make_ctx, instant, monkeypatch):
    """It must not compute the colour once and sleep forever."""
    _freeze_clock(monkeypatch, 12)
    ctx = make_ctx()
    await drive(Circadian(), ctx, lambda c: len(c.logs) >= 3)
    assert len(ctx.logs) >= 3
    assert instant.sleeps.count(27) >= 2, "the schedule is not re-evaluated"


def test_describe_and_name():
    assert Circadian().name == "circadian"
    assert Circadian().describe().strip()
