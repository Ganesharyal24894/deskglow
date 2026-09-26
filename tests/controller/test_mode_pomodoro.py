"""Pomodoro mode: the strip's colour is the phase, and the last minute warns.

A virtual clock makes a 25-minute pomodoro run in a few milliseconds."""
import pytest
from mode_clock import drive, install

from deskglow.controller.modes import pomodoro as pom_mod
from deskglow.controller.modes.pomodoro import BREAK_COLOR, DONE_COLOR, FOCUS_COLOR, Pomodoro


@pytest.fixture
def virtual(monkeypatch):
    return install(monkeypatch, pom_mod)


def _focus_logs(ctx):
    return [line for line in ctx.logs if "focus round" in line]


def _break_logs(ctx):
    return [line for line in ctx.logs if "break" in line]


def _done_watcher():
    """Predicate: wait for the 'done' log, then for 30 more frames after it."""
    state = {"n": None}

    def until(c):
        if state["n"] is None:
            if any("all rounds done" in line for line in c.logs):
                state["n"] = len(c.device.colors)
            return False
        return len(c.device.colors) >= state["n"] + 30

    return state, until


# ------------------------------------------------------------- sequencing --

async def test_phases_alternate_focus_break_focus_for_every_round(make_ctx, virtual):
    """focus -> break -> focus -> break -> focus, and nothing else."""
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=3), ctx, until)
    phases = [line for line in ctx.logs if "focus round" in line or "break" in line]
    assert len(phases) == 5
    assert "focus round 1/3" in phases[0]
    assert "break" in phases[1]
    assert "focus round 2/3" in phases[2]
    assert "break" in phases[3]
    assert "focus round 3/3" in phases[4]


async def test_logs_name_the_round_numbers(make_ctx, virtual):
    """The user reads the round counter out of the daemon log."""
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=4), ctx, until)
    focus = _focus_logs(ctx)
    assert [f"{i}/4" in line for i, line in enumerate(focus, 1)] == [True] * 4
    assert len(focus) == 4


async def test_no_break_after_the_final_round(make_ctx, virtual):
    """Ending on a break would leave the strip green after the session ends."""
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=3), ctx, until)
    assert len(_break_logs(ctx)) == 2, "expected rounds-1 breaks"
    last_focus = max(i for i, line in enumerate(ctx.logs) if "focus round" in line)
    assert not any("break" in line for line in ctx.logs[last_focus:])


async def test_single_round_has_no_break_at_all(make_ctx, virtual):
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=1), ctx, until)
    assert _break_logs(ctx) == []
    assert len(_focus_logs(ctx)) == 1


async def test_settles_on_done_colour_forever(make_ctx, virtual):
    """After the last round the strip holds DONE_COLOR and stops animating."""
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=2), ctx, until)
    tail = ctx.device.colors[state["n"]:]
    assert len(tail) >= 30
    assert set(tail) == {DONE_COLOR}


async def test_zero_rounds_goes_straight_to_done(make_ctx, virtual):
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=25, brk=5, rounds=0), ctx, until)
    assert _focus_logs(ctx) == []
    assert set(ctx.device.colors) == {DONE_COLOR}


async def test_focus_and_break_use_distinct_colours(make_ctx, virtual):
    """You must be able to tell the phase apart at a glance."""
    ctx = make_ctx()
    state, until = _done_watcher()
    await drive(Pomodoro(work=0.01, brk=0.01, rounds=2), ctx, until)
    assert FOCUS_COLOR != BREAK_COLOR != DONE_COLOR
    hues = {tuple(round(c / max(col) if max(col) else 0, 1) for c in col)
            for col in ctx.device.colors}
    assert len(hues) >= 3, "phases are not visually distinguishable"


# ------------------------------------------------------ steady vs pulsing ---

async def test_phase_is_steady_outside_the_final_minute(make_ctx, virtual, monkeypatch):
    """Most of a focus block is a rock-steady colour -- no distracting motion."""
    monkeypatch.setattr(pom_mod, "FPS", 1)      # one frame per virtual second
    ctx = make_ctx()
    await Pomodoro()._phase(ctx, FOCUS_COLOR, 2.0)   # 120s = 120 frames
    assert len(ctx.device.colors) == 120
    assert set(ctx.device.colors[:60]) == {FOCUS_COLOR}


async def test_final_minute_of_a_phase_pulses(make_ctx, virtual, monkeypatch):
    """The last 60 seconds breathe, warning that the phase is about to end."""
    monkeypatch.setattr(pom_mod, "FPS", 1)
    ctx = make_ctx()
    await Pomodoro()._phase(ctx, FOCUS_COLOR, 2.0)
    final = ctx.device.colors[60:]
    assert len(final) == 60
    lum = [sum(c) for c in final]
    assert len(set(lum)) > 5, "the final minute is not pulsing"
    assert min(lum) < sum(FOCUS_COLOR) * 0.75, "the pulse never dims"
    assert max(lum) <= sum(FOCUS_COLOR)
    assert min(lum) > sum(FOCUS_COLOR) * 0.4, "the pulse dips too dark"
    ups = sum(1 for a, b in zip(lum, lum[1:], strict=False) if b > a)
    downs = sum(1 for a, b in zip(lum, lum[1:], strict=False) if b < a)
    assert ups > 5 and downs > 5, "the pulse does not oscillate"


async def test_a_phase_without_warning_never_pulses(make_ctx, virtual, monkeypatch):
    """warn=False keeps the whole phase steady."""
    monkeypatch.setattr(pom_mod, "FPS", 1)
    ctx = make_ctx()
    await Pomodoro()._phase(ctx, BREAK_COLOR, 2.0, warn=False)
    assert set(ctx.device.colors) == {BREAK_COLOR}


async def test_short_phase_pulses_throughout(make_ctx, virtual, monkeypatch):
    """A phase shorter than a minute is entirely inside its own final minute."""
    monkeypatch.setattr(pom_mod, "FPS", 1)
    ctx = make_ctx()
    await Pomodoro()._phase(ctx, FOCUS_COLOR, 0.5)   # 30s
    lum = [sum(c) for c in ctx.device.colors]
    assert len(lum) == 30
    assert len(set(lum)) > 5


async def test_phase_ends_after_the_configured_duration(make_ctx, virtual, monkeypatch):
    """minutes are minutes: 3 minutes at 1 fps is 180 frames, then it returns."""
    monkeypatch.setattr(pom_mod, "FPS", 1)
    ctx = make_ctx()
    await Pomodoro()._phase(ctx, FOCUS_COLOR, 3.0)
    assert len(ctx.device.colors) == 180


# ------------------------------------------------------------- transitions --

async def test_transition_pulse_marks_a_new_phase(make_ctx, virtual):
    """A short triple-pulse announces each phase change."""
    ctx = make_ctx()
    await Pomodoro()._pulse(ctx, BREAK_COLOR, times=3, period=0.6)
    lum = [sum(c) for c in ctx.device.colors]
    assert 52 <= len(lum) <= 56, "~3 x 0.6s at 30 fps"
    assert max(lum) == pytest.approx(sum(BREAK_COLOR), rel=0.02)
    assert min(lum) == pytest.approx(sum(BREAK_COLOR) * 0.35, rel=0.05)
    diffs = [b - a for a, b in zip(lum, lum[1:], strict=False) if b != a]
    turns = sum(1 for a, b in zip(diffs, diffs[1:], strict=False) if a * b < 0)
    assert turns >= 5, "expected three distinct pulses"


# ------------------------------------------------------------------ misc ----

async def test_respects_the_brightness_ceiling(make_ctx, virtual, monkeypatch):
    monkeypatch.setattr(pom_mod, "FPS", 1)
    ctx = make_ctx(state={"max_brightness": 50})
    await Pomodoro()._phase(ctx, FOCUS_COLOR, 0.2, warn=False)
    assert set(ctx.device.colors) == {tuple(int(c * 0.5) for c in FOCUS_COLOR)}


def test_constructor_coerces_types():
    m = Pomodoro(work="25", brk=5.5, rounds="4")
    assert (m.work, m.brk, m.rounds) == (25.0, 5.5, 4)


def test_describe_and_name():
    m = Pomodoro(work=50, brk=10, rounds=2)
    assert m.name == "pomodoro"
    assert m.describe() == "pomodoro 50/10x2"
