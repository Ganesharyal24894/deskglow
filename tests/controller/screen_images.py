"""Synthetic float32 screen images for the sampler tests."""
import numpy as np

from deskglow.controller.modes.sampler import downsample, reduce


def solid(rgb, size=64):
    """A size x size image of one colour, in _grab's float32 layout."""
    arr = np.zeros((size, size, 3), dtype=np.float32)
    arr[:, :] = rgb
    return arr


def bordered(border_rgb, centre_rgb, size=96, thickness=14):
    """An image with a coloured border and a differently-coloured centre."""
    arr = solid(border_rgb, size)
    arr[thickness:-thickness, thickness:-thickness] = centre_rgb
    return arr


def grey_with_patch(grey=100, patch_rgb=(255, 0, 0), size=100, patch=10):
    """A mostly-grey image with a small saturated patch (a few percent)."""
    arr = solid((grey, grey, grey), size)
    arr[:patch, :patch] = patch_rgb
    return arr


class Feed:
    """Feeds an image through the same path Sampler.sample() uses."""

    def __init__(self):
        self.img = solid((0, 0, 0))

    def feed(self, img):
        self.img = img

    def sample(self, _rect, style="average"):
        return reduce(downsample(self.img), style)
