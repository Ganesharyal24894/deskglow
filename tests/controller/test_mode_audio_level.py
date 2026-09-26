"""Audio-reactive mode: brightness follows the loudness of the captured audio."""
import pytest
from audio_mode_support import LOUD, QUIET, SILENCE, install

from deskglow.controller.modes.audio import DECAY, FLOOR, Audio


@pytest.fixture
def h(monkeypatch, make_ctx):
    return install(monkeypatch, make_ctx)


async def test_loud_audio_is_brighter_than_silence(h):
    """The whole point: the strip tracks the level."""
    quiet = await h.run(Audio(rgb=[255, 255, 255]), [SILENCE])
    loud = await h.run(Audio(rgb=[255, 255, 255]), [LOUD])
    assert sum(loud.device.colors[0]) > sum(quiet.device.colors[0])


async def test_brightness_is_ordered_by_level(h):
    out = []
    for chunk in (SILENCE, QUIET, LOUD):
        ctx = await h.run(Audio(rgb=[255, 255, 255]), [chunk])
        out.append(ctx.device.colors[0][0])
    assert out[0] < out[1] < out[2]


async def test_silence_never_goes_fully_dark(h):
    """FLOOR keeps a visible glow, so a paused track does not look broken."""
    ctx = await h.run(Audio(rgb=[255, 255, 255]), [SILENCE] * 20)
    for col in ctx.device.colors:
        assert min(col) > 0, "silence must still glow"
    assert ctx.device.colors[-1][0] == pytest.approx(255 * FLOOR, abs=1)


async def test_full_scale_audio_reaches_full_brightness(h):
    ctx = await h.run(Audio(rgb=[255, 255, 255]), [LOUD])
    assert ctx.device.colors[0] == (255, 255, 255)


async def test_envelope_decays_gradually_instead_of_snapping_down(h):
    """VU-meter behaviour: fast attack, slow release."""
    ctx = await h.run(Audio(rgb=[255, 255, 255]), [LOUD] + [SILENCE] * 12)
    lvl = [c[0] for c in ctx.device.colors]
    assert lvl[0] == 255
    assert lvl[1] > 200, "level collapsed to the floor in one chunk"
    for a, b in zip(lvl, lvl[1:], strict=False):
        assert b < a, "envelope must fall monotonically once the sound stops"
    assert lvl[1] / 255.0 == pytest.approx(FLOOR + (1 - FLOOR) * DECAY, abs=0.01)
    assert lvl[-1] < lvl[1]


async def test_attack_is_immediate(h):
    """A transient must light up on the very next frame, not fade in."""
    ctx = await h.run(Audio(rgb=[255, 255, 255]), [SILENCE] * 3 + [LOUD] + [SILENCE])
    assert [c[0] for c in ctx.device.colors][3] == 255


async def test_a_fixed_base_rgb_is_respected(h):
    """With an explicit colour the hue never moves; only brightness does."""
    ctx = await h.run(Audio(rgb=[200, 100, 50]), [LOUD, QUIET, SILENCE, LOUD, SILENCE])
    assert len({(round(c[1] / c[0], 2), round(c[2] / c[0], 2))
                for c in ctx.device.colors}) == 1
    for col in ctx.device.colors:
        assert col[1] == pytest.approx(col[0] * 0.5, abs=1)
        assert col[2] == pytest.approx(col[0] * 0.25, abs=1)


async def test_without_a_base_the_hue_drifts(h):
    """No colour given => a slow rainbow drift under the level envelope."""
    ctx = await h.run(Audio(), [LOUD] * 30)
    cols = ctx.device.colors
    assert len(set(cols)) > 10, "hue is not drifting"
    assert len({round(c[1] / max(c[0], 1), 2) for c in cols}) > 5


async def test_colours_are_always_valid_rgb_triples(h):
    ctx = await h.run(Audio(), [LOUD, SILENCE, QUIET] * 5)
    for col in ctx.device.colors:
        assert len(col) == 3
        for c in col:
            assert isinstance(c, int) and 0 <= c <= 255


async def test_respects_the_brightness_ceiling(h):
    ctx = await h.run(Audio(rgb=[255, 255, 255]), [LOUD], state={"max_brightness": 50})
    assert ctx.device.colors[0] == (127, 127, 127)
