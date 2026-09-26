"""Circadian mode's schedule: colour temperature/brightness keypoints by hour."""
import pytest

from deskglow.controller.modes.circadian import KEYPOINTS, _interp


# ----------------------------------------------------------------- _interp --

def test_keypoints_are_sorted_and_wrap_a_full_day():
    """The table must cover 0..24 with no gaps, and wrap back to its start."""
    hours = [h for h, _k, _b in KEYPOINTS]
    assert hours == sorted(hours)
    assert hours[0] == 0 and hours[-1] == 24
    assert KEYPOINTS[0][1:] == KEYPOINTS[-1][1:], "midnight must wrap onto itself"


@pytest.mark.parametrize("hour,kelvin,bri", KEYPOINTS)
def test_interp_returns_each_keypoint_exactly_at_its_hour(hour, kelvin, bri):
    """No drift at the anchors: the curve passes through every keypoint."""
    assert _interp(hour) == pytest.approx((kelvin, bri))


def test_interp_is_monotonic_between_two_keypoints():
    """Between 08:00 (4000K/0.80) and 11:00 (5800K/1.00) both rise steadily."""
    samples = [_interp(8 + i * 0.1) for i in range(31)]
    kelvins = [k for k, _b in samples]
    bris = [b for _k, b in samples]
    assert kelvins == sorted(kelvins)
    assert bris == sorted(bris)
    assert kelvins[0] == pytest.approx(4000) and kelvins[-1] == pytest.approx(5800)


def test_interp_is_monotonic_downwards_in_the_evening():
    """19:00 -> 21:00 must get warmer and dimmer, never brighter."""
    samples = [_interp(19 + i * 0.1) for i in range(21)]
    kelvins = [k for k, _b in samples]
    bris = [b for _k, b in samples]
    assert kelvins == sorted(kelvins, reverse=True)
    assert bris == sorted(bris, reverse=True)


def test_interp_halfway_is_the_midpoint_of_the_two_keypoints():
    k, b = _interp(9.5)          # midway between (8, 4000, .80) and (11, 5800, 1.0)
    assert k == pytest.approx(4000 + (5800 - 4000) * 0.5)
    assert b == pytest.approx(0.80 + (1.00 - 0.80) * 0.5)


@pytest.mark.parametrize("hour", [0, 0.0, 23.99, 23.999999, 12.5, 6.0001])
def test_interp_handles_the_whole_day_without_raising(hour):
    k, b = _interp(hour)
    assert 1000 <= k <= 10000
    assert 0.0 <= b <= 1.0


@pytest.mark.parametrize("hour", [-1, -0.001, 24, 24.5, 100, 1e9])
def test_interp_survives_out_of_range_hours(hour):
    """A bad clock must not crash the daemon; fall back to the wrap keypoint."""
    k, b = _interp(hour)
    assert (k, b) == pytest.approx((KEYPOINTS[-1][1], KEYPOINTS[-1][2]))


def test_interp_never_returns_a_zero_brightness():
    """Even at 3am the strip stays visible."""
    for i in range(0, 2400):
        _k, b = _interp(i / 100.0)
        assert b > 0.0
