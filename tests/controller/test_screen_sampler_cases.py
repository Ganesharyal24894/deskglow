"""Screen colour reduction: style-specific behaviour on synthetic images."""
import numpy as np
import pytest
from screen_images import Feed, bordered, grey_with_patch, solid

from deskglow.controller.modes.sampler import SAMPLE_WIDTH, Sampler, downsample

RECT = {"left": 0, "top": 0, "width": 640, "height": 480}


@pytest.fixture
def sampler():
    return Feed()


def test_edge_style_follows_the_border_not_the_centre(sampler):
    """'edge' is the bias-light style: a red border beats a blue centre."""
    sampler.feed(bordered((255, 0, 0), (0, 0, 255)))
    r, g, b = sampler.sample(RECT, "edge")
    assert r > b
    assert r > 200 and b < 55


def test_average_style_follows_the_centre_not_the_border(sampler):
    """Contrast check: 'average' on the same image is dominated by the centre."""
    sampler.feed(bordered((255, 0, 0), (0, 0, 255)))
    r, _g, b = sampler.sample(RECT, "average")
    assert b > r, "the large blue centre should dominate a plain average"


def test_average_style_is_the_arithmetic_mean(sampler):
    """'average' is exactly the per-channel mean of the grabbed pixels."""
    img = solid((0, 0, 0), size=10)
    img[:5] = (200, 100, 50)
    sampler.feed(img)
    assert sampler.sample(RECT, "average") == pytest.approx((100.0, 50.0, 25.0))


def test_vivid_style_is_driven_by_a_small_colourful_region(sampler):
    """A 1% red patch on a grey desktop still drives 'vivid' red."""
    sampler.feed(grey_with_patch())
    r, g, b = sampler.sample(RECT, "vivid")
    assert r > g and r > b
    assert r > 200


def test_dominant_style_is_driven_by_a_small_colourful_region(sampler):
    """'dominant' picks the most-weighted hue bucket, not the grey majority."""
    sampler.feed(grey_with_patch())
    r, g, b = sampler.sample(RECT, "dominant")
    assert r > g and r > b
    assert r > 200


def test_vivid_is_more_saturated_than_average(sampler):
    """'vivid' boosts saturation relative to a plain average of the same image."""
    import colorsys
    img = grey_with_patch(grey=140, patch_rgb=(255, 40, 40), patch=20)
    sampler.feed(img)
    vivid = sampler.sample(RECT, "vivid")
    avg = sampler.sample(RECT, "average")
    s_vivid = colorsys.rgb_to_hsv(*(c / 255.0 for c in vivid))[1]
    s_avg = colorsys.rgb_to_hsv(*(c / 255.0 for c in avg))[1]
    assert s_vivid > s_avg


def test_dominant_ignores_a_large_desaturated_background(sampler):
    """Half the screen dark-grey, a quarter saturated cyan -> cyan wins."""
    img = solid((30, 30, 30), size=80)
    img[:20, :20] = (0, 200, 200)
    sampler.feed(img)
    r, g, b = sampler.sample(RECT, "dominant")
    assert g > r and b > r


def test_unknown_style_falls_back_to_average(sampler):
    """An unrecognised style name behaves like 'average' rather than raising."""
    sampler.feed(bordered((255, 0, 0), (0, 0, 255)))
    assert sampler.sample(RECT, "no-such-style") == sampler.sample(RECT, "average")


def test_default_style_is_average(sampler):
    """sample() defaults to 'average'."""
    sampler.feed(bordered((255, 0, 0), (0, 0, 255)))
    assert sampler.sample(RECT) == sampler.sample(RECT, "average")


def test_edge_handles_a_short_image_without_crashing(sampler):
    """The border band is at least 2px, so tiny grabs still work."""
    sampler.feed(solid((10, 20, 30), size=4))
    out = sampler.sample(RECT, "edge")
    assert out == pytest.approx((10.0, 20.0, 30.0))


def test_sampler_is_reusable_across_styles(sampler):
    """One Sampler instance serves repeated calls without accumulating state."""
    sampler.feed(solid((255, 0, 0)))
    first = sampler.sample(RECT, "vivid")
    sampler.feed(solid((0, 0, 255)))
    second = sampler.sample(RECT, "vivid")
    assert first != second
    assert second[2] > second[0]


# ------------------------------------------------ Sampler over a ScreenSource --

class _Source:
    def __init__(self, img):
        self.img = img
        self.rects = []

    async def grab(self, rect):
        self.rects.append(rect)
        return self.img


async def test_sample_passes_the_rect_through_to_grab():
    """The rect the caller asks for is the rect that gets grabbed."""
    src = _Source(np.zeros((8, 8, 3), dtype=np.uint8))
    await Sampler(src).sample(RECT, "average")
    assert src.rects[-1] is RECT


async def test_sampler_reduces_a_uint8_grab():
    """A driver hands back uint8 pixels; the sampler turns them into a colour."""
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:5] = (200, 100, 50)
    assert await Sampler(_Source(img)).sample(RECT) == pytest.approx((100.0, 50.0, 25.0))


def test_downsample_keeps_a_sample_width_grid_as_float32():
    """Wide grabs are strided down to ~SAMPLE_WIDTH columns before reducing."""
    img = np.zeros((100, SAMPLE_WIDTH * 4, 3), dtype=np.uint8)
    out = downsample(img)
    assert out.dtype == np.float32
    assert out.shape == (25, SAMPLE_WIDTH, 3)


def test_downsample_leaves_a_narrow_grab_whole():
    img = np.full((7, 50, 3), 9, dtype=np.uint8)
    out = downsample(img)
    assert out.shape == (7, 50, 3) and float(out[0, 0, 0]) == 9.0
