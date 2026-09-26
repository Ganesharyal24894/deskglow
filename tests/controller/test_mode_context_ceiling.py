"""ModeContext: the global brightness ceiling, raw frames bypassing it, the
injected services, and the Mode base class."""
import pytest
from fakes import make_services

from deskglow.controller.modes.base import Mode

# ------------------------------------------------------- brightness ceiling --

async def test_set_applies_the_brightness_ceiling_as_an_rgb_scale(make_ctx):
    """max_brightness is a percentage ceiling scaled onto every channel."""
    ctx = make_ctx(state={"max_brightness": 50})
    await ctx.set(200, 100, 60)
    assert ctx.device.colors == [(100, 50, 30)]


async def test_ceiling_of_100_passes_the_colour_through_untouched(make_ctx):
    ctx = make_ctx(state={"max_brightness": 100})
    await ctx.set(255, 180, 110)
    assert ctx.device.colors == [(255, 180, 110)]


async def test_ceiling_of_zero_turns_the_strip_off(make_ctx):
    """0% is a legal ceiling and must mean "dark", not "unchanged"."""
    ctx = make_ctx(state={"max_brightness": 0})
    await ctx.set(255, 255, 255)
    assert ctx.device.colors == [(0, 0, 0)]


async def test_missing_max_brightness_defaults_to_full(make_ctx):
    """A state dict from an older daemon has no ceiling key: assume 100%."""
    ctx = make_ctx(state={})
    await ctx.set(255, 128, 0)
    assert ctx.device.colors == [(255, 128, 0)]


@pytest.mark.parametrize("ceiling", [0, 1, 33, 50, 99, 100])
async def test_every_write_is_a_valid_rgb_triple_for_any_legal_ceiling(make_ctx, ceiling):
    """Whatever the ceiling, the device only ever sees 0-255 integers."""
    ctx = make_ctx(state={"max_brightness": ceiling})
    for rgb in [(0, 0, 0), (255, 255, 255), (1, 2, 3), (254, 130, 7)]:
        await ctx.set(*rgb)
    for col in ctx.device.colors:
        assert len(col) == 3
        for c in col:
            assert isinstance(c, int)
            assert 0 <= c <= 255


async def test_ceiling_above_100_is_clamped_and_never_overdrives(make_ctx):
    """A ceiling can only dim. 150% must not push channels past their value."""
    ctx = make_ctx(state={"max_brightness": 150})
    await ctx.set(200, 100, 60)
    assert ctx.device.colors == [(200, 100, 60)]


async def test_negative_ceiling_is_clamped_to_off(make_ctx):
    ctx = make_ctx(state={"max_brightness": -20})
    await ctx.set(255, 255, 255)
    assert ctx.device.colors == [(0, 0, 0)]


@pytest.mark.parametrize("junk", [None, "bright", [], {}, object()])
async def test_a_junk_ceiling_falls_back_to_full_instead_of_crashing(make_ctx, junk):
    """A hand-edited or stale state file must not take the running mode down."""
    ctx = make_ctx(state={"max_brightness": junk})
    await ctx.set(10, 20, 30)
    assert ctx.device.colors == [(10, 20, 30)]


async def test_a_numeric_string_ceiling_still_works(make_ctx):
    ctx = make_ctx(state={"max_brightness": "50"})
    await ctx.set(200, 100, 60)
    assert ctx.device.colors == [(100, 50, 30)]


async def test_ceiling_never_brightens_a_colour(make_ctx):
    """It is a *ceiling*: the output can only ever be <= the requested colour."""
    for ceiling in (0, 25, 50, 75, 100):
        ctx = make_ctx(state={"max_brightness": ceiling})
        await ctx.set(200, 100, 60)
        r, g, b = ctx.device.colors[-1]
        assert (r, g, b) <= (200, 100, 60)


async def test_raw_frames_bypass_the_brightness_scaling(make_ctx):
    """raw() carries an already-encoded protocol frame; it must go out verbatim."""
    ctx = make_ctx(state={"max_brightness": 10})
    frame = bytes([0x7E, 0x00, 0x03, 0x8A, 0x03, 0x00, 0x00, 0x00, 0xEF])
    await ctx.raw(frame)
    assert ctx.device.frames == [frame]


# ---------------------------------------------------------------- services --

def test_encoder_is_the_injected_services_encoder(make_ctx):
    """Modes render frames with the encoder the app wired in for the preset."""
    svc = make_services(encoder=object())
    ctx = make_ctx(services=svc)
    assert ctx.encoder is svc.encoder
    assert ctx.services is svc


# ------------------------------------------------------------- Mode itself --

async def test_mode_run_is_abstract():
    """The base class is an interface: subclasses must implement run()."""
    with pytest.raises(NotImplementedError):
        await Mode().run(None)


def test_mode_describe_defaults_to_the_mode_name():
    assert Mode().describe() == "base"
