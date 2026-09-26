"""Screen colour reduction: every style on synthetic images (no display)."""
import pytest
from screen_images import Feed, bordered, solid

from deskglow.controller.modes.sampler import STYLES


@pytest.fixture
def sampler():
    return Feed()


RECT = {"left": 0, "top": 0, "width": 640, "height": 480}


def test_styles_constant():
    """The four supported sampling styles."""
    assert STYLES == ("average", "vivid", "dominant", "edge")


@pytest.mark.parametrize("style", STYLES)
def test_solid_red_is_red_in_every_style(sampler, style):
    """A fully red screen must drive the strip red whichever style is chosen."""
    sampler.feed(solid((255, 0, 0)))
    r, g, b = sampler.sample(RECT, style)
    assert r > 200
    assert r > g and r > b


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("rgb", [(0, 255, 0), (0, 0, 255)])
def test_solid_primaries_are_preserved(sampler, style, rgb):
    """Green and blue screens map to green and blue, in every style."""
    sampler.feed(solid(rgb))
    out = sampler.sample(RECT, style)
    dominant = max(range(3), key=lambda i: out[i])
    assert dominant == rgb.index(255)


@pytest.mark.parametrize("style", STYLES)
def test_greyscale_falls_back_to_the_mean(sampler, style):
    """A greyscale screen has no hue to boost: return the plain mean."""
    sampler.feed(solid((128, 128, 128)))
    out = sampler.sample(RECT, style)
    assert all(c == pytest.approx(128.0, abs=1.0) for c in out)


@pytest.mark.parametrize("style", STYLES)
def test_black_screen_stays_black(sampler, style):
    """An all-black grab must not divide-by-zero its way to a bright colour."""
    sampler.feed(solid((0, 0, 0)))
    out = sampler.sample(RECT, style)
    assert all(c == pytest.approx(0.0, abs=1.0) for c in out)


@pytest.mark.parametrize("style", STYLES)
def test_sample_returns_three_floats_in_range(sampler, style):
    """Every style returns a 3-tuple of floats inside 0..255."""
    sampler.feed(bordered((255, 0, 0), (0, 0, 255)))
    out = sampler.sample(RECT, style)
    assert isinstance(out, tuple) and len(out) == 3
    assert all(isinstance(c, float) for c in out)
    assert all(-0.001 <= c <= 255.001 for c in out)
