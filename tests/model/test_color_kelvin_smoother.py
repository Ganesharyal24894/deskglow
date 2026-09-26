"""deskglow.model.color: colour temperature and the Smoother.

Pure functions only: no device, no I/O, no timing.
"""
import pytest

from deskglow.model import color


# ------------------------------------------------------- kelvin_to_rgb ------

KELVINS = [1000, 1500, 2000, 2700, 3500, 4500, 5500, 6500, 8000, 10000, 15000,
           25000, 40000]


@pytest.mark.parametrize("kelvin", [1000, 1500, 2000, 2700])
def test_kelvin_warm_end_is_red_dominant(kelvin):
    """Candle/incandescent temperatures are red-dominant."""
    r, g, b = color.kelvin_to_rgb(kelvin)
    assert r == 255
    assert r > g > b


@pytest.mark.parametrize("kelvin", [10000, 20000, 40000])
def test_kelvin_cool_end_is_blue_dominant(kelvin):
    """Deep-blue-sky temperatures are blue-dominant."""
    r, g, b = color.kelvin_to_rgb(kelvin)
    assert b == 255
    assert b > r


def test_kelvin_is_monotonic_across_the_range():
    """Red never rises and blue never falls as the temperature increases."""
    vals = [color.kelvin_to_rgb(k) for k in KELVINS]
    reds = [v[0] for v in vals]
    blues = [v[2] for v in vals]
    assert reds == sorted(reds, reverse=True)
    assert blues == sorted(blues)


@pytest.mark.parametrize("kelvin", [0, -5000, 500, 999])
def test_kelvin_clamps_below_1000(kelvin):
    """Anything under 1000 K behaves as 1000 K rather than blowing up."""
    assert color.kelvin_to_rgb(kelvin) == color.kelvin_to_rgb(1000)


@pytest.mark.parametrize("kelvin", [40001, 100000, 10**9])
def test_kelvin_clamps_above_40000(kelvin):
    """Anything over 40000 K behaves as 40000 K."""
    assert color.kelvin_to_rgb(kelvin) == color.kelvin_to_rgb(40000)


@pytest.mark.parametrize("kelvin", KELVINS)
def test_kelvin_always_returns_valid_bytes(kelvin):
    """Every temperature yields three ints in 0..255."""
    out = color.kelvin_to_rgb(kelvin)
    assert len(out) == 3
    assert all(isinstance(c, int) and 0 <= c <= 255 for c in out)


def test_kelvin_near_daylight_is_near_white():
    """~6500 K is the neutral-white reference point."""
    r, g, b = color.kelvin_to_rgb(6500)
    assert min(r, g, b) > 235


# ------------------------------------------------------------- Smoother -----

def test_smoother_starts_at_its_start_colour():
    """A fresh Smoother reports the colour it was seeded with."""
    s = color.Smoother(alpha=0.5, start=(10, 20, 30))
    assert tuple(int(c) for c in s.cur) == (10, 20, 30)


def test_smoother_converges_toward_target():
    """Repeated steps close in on the target monotonically."""
    s = color.Smoother(alpha=0.3, start=(0, 0, 0))
    prev = -1
    for _ in range(60):
        out = s.step((255, 255, 255))
        assert out[0] >= prev
        prev = out[0]
    assert s.step((255, 255, 255)) == (255, 255, 255)


def test_smoother_step_never_overshoots():
    """One step lands strictly between the current value and the target."""
    s = color.Smoother(alpha=0.5, start=(0, 0, 0))
    out = s.step((100, 100, 100))
    assert out == (50, 50, 50)


def test_smoother_alpha_one_snaps_to_target():
    """alpha=1 means no smoothing at all."""
    s = color.Smoother(alpha=1.0, start=(0, 0, 0))
    assert s.step((7, 8, 9)) == (7, 8, 9)


def test_smoother_alpha_zero_never_moves():
    """alpha=0 freezes the output."""
    s = color.Smoother(alpha=0.0, start=(11, 22, 33))
    for _ in range(10):
        assert s.step((255, 0, 0)) == (11, 22, 33)


def test_smoother_smaller_alpha_moves_slower():
    """Alpha is the per-step fraction of the remaining distance."""
    slow = color.Smoother(alpha=0.05, start=(0, 0, 0)).step((255, 255, 255))
    fast = color.Smoother(alpha=0.5, start=(0, 0, 0)).step((255, 255, 255))
    assert slow[0] < fast[0]


def test_smoother_set_jumps_without_smoothing():
    """set() teleports the smoother, bypassing the EMA."""
    s = color.Smoother(alpha=0.01, start=(0, 0, 0))
    s.set((200, 100, 50))
    assert s.step((200, 100, 50)) == (200, 100, 50)


def test_smoother_set_then_step_smooths_from_the_new_point():
    """After set(), the next step starts from the value that was set."""
    s = color.Smoother(alpha=0.5, start=(0, 0, 0))
    s.set((0, 0, 0))
    assert s.step((200, 200, 200)) == (100, 100, 100)


def test_smoother_retargets_midflight():
    """Changing the target mid-flight redirects the smoother, no state reset."""
    s = color.Smoother(alpha=0.5, start=(0, 0, 0))
    s.step((255, 255, 255))          # now at ~127
    out = s.step((0, 0, 0))          # pulled back toward black
    assert 0 < out[0] < 127


def test_smoother_output_is_always_byte_sized():
    """step() always emits clamped ints, whatever the target."""
    s = color.Smoother(alpha=0.5, start=(0, 0, 0))
    out = s.step((1000, -1000, 128))
    assert all(isinstance(c, int) and 0 <= c <= 255 for c in out)
