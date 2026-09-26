"""deskglow.model.color: clamps, HSV, scale, lerp, gamma, saturate.

Pure functions only: no device, no I/O, no timing.
"""
import colorsys

import pytest

from deskglow.model import color


# --------------------------------------------------------------- clamps -----

@pytest.mark.parametrize("value,expected", [
    (-1, 0), (-1000, 0), (0, 0), (127, 127), (255, 255), (256, 255), (1e9, 255),
    (127.4, 127), (127.5, 128), (254.9, 255),
])
def test_clamp8(value, expected):
    """clamp8 rounds to the nearest int and pins the result into 0..255."""
    assert color.clamp8(value) == expected


@pytest.mark.parametrize("value,expected", [
    (-0.5, 0.0), (0.0, 0.0), (0.25, 0.25), (1.0, 1.0), (1.5, 1.0),
])
def test_clampf_default_unit_range(value, expected):
    """clampf defaults to a 0..1 range."""
    assert color.clampf(value) == pytest.approx(expected)


@pytest.mark.parametrize("value,expected", [(5, 10), (10, 10), (50, 50), (99, 90)])
def test_clampf_explicit_range(value, expected):
    """clampf honours explicit lo/hi bounds."""
    assert color.clampf(value, 10, 90) == pytest.approx(expected)


# ------------------------------------------------------------------ hsv -----

@pytest.mark.parametrize("h,s,v,expected", [
    (0.0, 1.0, 1.0, (255, 0, 0)),
    (1 / 3, 1.0, 1.0, (0, 255, 0)),
    (2 / 3, 1.0, 1.0, (0, 0, 255)),
    (0.0, 0.0, 1.0, (255, 255, 255)),
    (0.0, 0.0, 0.0, (0, 0, 0)),
])
def test_hsv_to_rgb_primaries(h, s, v, expected):
    """The HSV primaries land exactly on the RGB primaries."""
    assert color.hsv_to_rgb(h, s, v) == expected


@pytest.mark.parametrize("h", [1.0, 2.5, -0.25])
def test_hsv_to_rgb_wraps_hue(h):
    """Hue is taken modulo 1, so animations may keep incrementing it forever."""
    assert color.hsv_to_rgb(h, 1.0, 1.0) == color.hsv_to_rgb(h % 1.0, 1.0, 1.0)


@pytest.mark.parametrize("s,v,expected", [
    (-1.0, 2.0, (255, 255, 255)),    # s -> 0, v -> 1  => white
    (5.0, -3.0, (0, 0, 0)),          # s -> 1, v -> 0  => black
])
def test_hsv_to_rgb_clamps_s_and_v(s, v, expected):
    """Out-of-range saturation/value are clamped into 0..1, never wrapped."""
    assert color.hsv_to_rgb(0.0, s, v) == expected


@pytest.mark.parametrize("rgb", [
    (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (0, 0, 0),
    (12, 200, 90), (137, 42, 219), (128, 128, 128),
])
def test_rgb_to_hsv_round_trip(rgb):
    """rgb -> hsv -> rgb returns the original colour (within rounding)."""
    h, s, v = color.rgb_to_hsv(rgb)
    assert color.hsv_to_rgb(h, s, v) == rgb


def test_rgb_to_hsv_matches_colorsys():
    """rgb_to_hsv is just colorsys on 0..1 floats; pin the normalisation."""
    assert color.rgb_to_hsv((255, 128, 0)) == colorsys.rgb_to_hsv(1.0, 128 / 255.0, 0.0)


# ---------------------------------------------------------------- scale -----

@pytest.mark.parametrize("factor,expected", [
    (0.0, (0, 0, 0)),
    (0.5, (50, 100, 128)),
    (1.0, (100, 200, 255)),
])
def test_scale_multiplies_each_channel(factor, expected):
    """scale() multiplies every channel by the factor."""
    assert color.scale((100, 200, 255), factor) == expected


@pytest.mark.parametrize("factor", [1.5, 10.0])
def test_scale_clamps_factor_above_one(factor):
    """A factor above 1 cannot brighten past the original colour."""
    assert color.scale((100, 200, 255), factor) == (100, 200, 255)


@pytest.mark.parametrize("factor", [-0.5, -10.0])
def test_scale_clamps_negative_factor_to_black(factor):
    """A negative factor is clamped to 0, i.e. black -- never a wrapped value."""
    assert color.scale((100, 200, 255), factor) == (0, 0, 0)


# ----------------------------------------------------------------- lerp -----

@pytest.mark.parametrize("t,expected", [
    (0.0, (0, 0, 0)),
    (0.5, (50, 100, 128)),
    (1.0, (100, 200, 255)),
])
def test_lerp_endpoints_and_midpoint(t, expected):
    """lerp walks linearly from a to b as t goes 0 -> 1."""
    assert color.lerp((0, 0, 0), (100, 200, 255), t) == expected


@pytest.mark.parametrize("t,expected", [(-1.0, (10, 20, 30)), (2.0, (200, 100, 50))])
def test_lerp_clamps_t(t, expected):
    """t outside 0..1 is clamped, so lerp never overshoots either endpoint."""
    assert color.lerp((10, 20, 30), (200, 100, 50), t) == expected


def test_lerp_is_symmetric_when_endpoints_swap():
    """lerp(a, b, t) == lerp(b, a, 1-t) for the midpoint."""
    a, b = (0, 40, 200), (255, 10, 0)
    assert color.lerp(a, b, 0.5) == color.lerp(b, a, 0.5)


# ---------------------------------------------------------------- gamma -----

@pytest.mark.parametrize("rgb", [(0, 0, 0), (255, 255, 255)])
def test_gamma_fixes_the_endpoints(rgb):
    """Gamma correction leaves pure black and pure white untouched."""
    assert color.gamma(rgb) == rgb


def test_gamma_brightens_midtones():
    """With g > 1 the 1/g exponent lifts midtones (that is the whole point)."""
    out = color.gamma((128, 128, 128))
    assert all(c > 128 for c in out)
    assert all(c <= 255 for c in out)


def test_gamma_is_monotonic():
    """A brighter input never produces a darker output."""
    outs = [color.gamma((v, v, v))[0] for v in range(0, 256, 5)]
    assert outs == sorted(outs)


def test_gamma_of_one_is_identity():
    """g=1 means no correction at all."""
    assert color.gamma((10, 128, 250), g=1.0) == (10, 128, 250)


# ------------------------------------------------------------- saturate -----

def test_saturate_above_one_makes_colour_more_vivid():
    """factor > 1 pushes a washed colour toward its pure hue."""
    washed = (200, 100, 100)
    out = color.saturate(washed, 2.0)
    assert color.rgb_to_hsv(out)[1] > color.rgb_to_hsv(washed)[1]
    assert out[0] > out[1] and out[0] > out[2]      # still red-dominant


def test_saturate_below_one_washes_colour_out():
    """factor < 1 moves the colour toward grey."""
    out = color.saturate((255, 0, 0), 0.25)
    assert color.rgb_to_hsv(out)[1] < 1.0
    assert out[1] > 0 and out[2] > 0


def test_saturate_clamps_saturation_at_one():
    """A huge factor cannot push saturation past fully-saturated."""
    assert color.saturate((255, 0, 0), 10.0) == (255, 0, 0)


def test_saturate_preserves_hue_and_value():
    """Only the S component changes."""
    src = (200, 120, 40)
    h0, _, v0 = color.rgb_to_hsv(src)
    h1, _, v1 = color.rgb_to_hsv(color.saturate(src, 1.2))
    assert h1 == pytest.approx(h0, abs=0.02)
    assert v1 == pytest.approx(v0, abs=0.01)


def test_saturate_of_grey_stays_grey():
    """Grey has no hue to boost."""
    assert color.saturate((128, 128, 128), 3.0) == (128, 128, 128)
