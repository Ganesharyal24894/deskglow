"""Calm mode: soft palette colours cross-fading, with a slow breathing envelope."""
import pytest
from mode_clock import drive, install

from deskglow.controller.modes import calm as calm_mod
from deskglow.controller.modes.calm import BREATH_MIN, PALETTE, Calm


@pytest.fixture
def virtual(monkeypatch):
    return install(monkeypatch, calm_mod)


# --------------------------------------------------------------- palette ----

def test_palette_is_soft_and_valid():
    """The whole point of calm mode: no harsh primaries, no out-of-range values."""
    assert len(PALETTE) >= 3
    for col in PALETTE:
        assert len(col) == 3
        for c in col:
            assert 0 <= c <= 255
        assert max(col) - min(col) < 150, f"{col} is too saturated for calm mode"
        assert max(col) > 0


async def test_every_output_is_a_valid_rgb_triple(make_ctx, virtual):
    """Nothing the mode emits may fall outside 0-255."""
    ctx = make_ctx()
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= 400)
    for col in ctx.device.colors:
        assert len(col) == 3
        for c in col:
            assert isinstance(c, int) and 0 <= c <= 255


async def test_colours_are_scaled_versions_of_the_current_palette_colour(
        make_ctx, virtual, monkeypatch):
    """With the cross-fade frozen, every frame is PALETTE[0] at some brightness."""
    monkeypatch.setattr(calm_mod, "FADE", 1e9)          # freeze on the first colour
    ctx = make_ctx()
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= 400)
    base = PALETTE[0]
    for col in ctx.device.colors:
        for i in range(3):
            # each channel is the same fraction of its palette channel (+/- rounding)
            assert col[i] <= base[i], "breath must never exceed the palette colour"
            expected = base[i] * (col[0] / base[0])
            assert abs(col[i] - expected) <= 1.5, f"{col} is not a scaled {base}"


async def test_breath_spans_breath_min_to_full_and_never_goes_dark(
        make_ctx, virtual, monkeypatch):
    """Brightness breathes between BREATH_MIN and 1.0 of the palette colour."""
    monkeypatch.setattr(calm_mod, "FADE", 1e9)
    ctx = make_ctx()
    # two full breath cycles at 30 fps
    frames = int(2.2 * calm_mod.BREATH_PERIOD * calm_mod.FPS)
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= frames)
    base = PALETTE[0]
    factors = [col[0] / base[0] for col in ctx.device.colors]
    assert max(factors) == pytest.approx(1.0, abs=0.02), "never reaches full brightness"
    assert min(factors) == pytest.approx(BREATH_MIN, abs=0.02), "breath floor is wrong"
    assert min(factors) > 0.0, "calm mode must never go fully dark"
    for col in ctx.device.colors:
        assert max(col) > 0


async def test_brightness_actually_oscillates(make_ctx, virtual, monkeypatch):
    """It breathes: brightness must go down again, not just ramp once."""
    monkeypatch.setattr(calm_mod, "FADE", 1e9)
    ctx = make_ctx()
    frames = int(2.2 * calm_mod.BREATH_PERIOD * calm_mod.FPS)
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= frames)
    lum = [sum(c) for c in ctx.device.colors]
    ups = sum(1 for a, b in zip(lum, lum[1:], strict=False) if b > a)
    downs = sum(1 for a, b in zip(lum, lum[1:], strict=False) if b < a)
    assert ups > 20 and downs > 20, "brightness did not breathe both ways"


async def test_cycles_through_every_palette_entry_in_order(
        make_ctx, virtual, monkeypatch):
    """Over time calm mode walks the whole palette and wraps back to the start."""
    monkeypatch.setattr(calm_mod, "BREATH_MIN", 1.0)    # pin breath at 1.0
    monkeypatch.setattr(calm_mod, "FADE", 1.0)          # one second per segment
    ctx = make_ctx()
    wanted = len(PALETTE) + 1
    seen = []
    cursor = [0]

    def _seen(c):
        while cursor[0] < len(c.device.colors):
            col = c.device.colors[cursor[0]]
            cursor[0] += 1
            if col in PALETTE and (not seen or seen[-1] != col):
                seen.append(col)
        return len(seen) >= wanted

    await drive(Calm(), ctx, lambda c: _seen(c), max_ticks=200000)
    assert seen[:len(PALETTE)] == PALETTE
    assert seen[len(PALETTE)] == PALETTE[0], "palette does not wrap around"


async def test_colours_between_palette_entries_are_interpolations(
        make_ctx, virtual, monkeypatch):
    """Mid-fade the colour lies between the two palette entries, channel by channel."""
    monkeypatch.setattr(calm_mod, "BREATH_MIN", 1.0)
    monkeypatch.setattr(calm_mod, "FADE", 1.0)
    ctx = make_ctx()
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= 30)
    a, b = PALETTE[0], PALETTE[1]
    for col in ctx.device.colors[:30]:
        for i in range(3):
            lo, hi = sorted((a[i], b[i]))
            assert lo - 1 <= col[i] <= hi + 1, f"{col} is outside {a}..{b}"


async def test_transitions_are_gradual(make_ctx, virtual):
    """No visible jumps: consecutive frames differ only slightly."""
    ctx = make_ctx()
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= 300)
    for prev, cur in zip(ctx.device.colors, ctx.device.colors[1:], strict=False):
        assert max(abs(p - c) for p, c in zip(prev, cur, strict=False)) <= 6


async def test_respects_the_brightness_ceiling(make_ctx, virtual, monkeypatch):
    """A 20% ceiling caps calm mode too."""
    monkeypatch.setattr(calm_mod, "FADE", 1e9)
    ctx = make_ctx(state={"max_brightness": 20})
    await drive(Calm(), ctx, lambda c: len(c.device.colors) >= 100)
    for col in ctx.device.colors:
        for i in range(3):
            assert col[i] <= PALETTE[0][i] * 0.2 + 1


def test_describe_and_name():
    assert Calm().name == "calm"
    assert Calm().describe().strip()
