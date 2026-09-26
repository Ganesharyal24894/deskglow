"""Audio-reactive mode: how it drives its AudioSource, and its own arguments."""
import asyncio

import pytest
from audio_mode_support import LOUD, SILENCE, install

from deskglow.controller.modes.audio import CHUNK, RATE, Audio, level_of


@pytest.fixture
def h(monkeypatch, make_ctx):
    return install(monkeypatch, make_ctx)


@pytest.mark.parametrize("kw,expected", [
    ({}, ("system", None)),
    ({"source": "mic"}, ("mic", None)),
    ({"target": "my.sink.monitor"}, ("system", "my.sink.monitor")),
])
async def test_starts_the_source_with_its_settings(h, kw, expected):
    """Source kind and explicit target are handed to the capture driver, which
    decides what they mean on this platform; rate and block size are fixed."""
    await h.run(Audio(**kw), [SILENCE])
    assert h.sources[-1].started == [(*expected, RATE, CHUNK)]


async def test_logs_what_it_is_capturing(h):
    ctx = await h.run(Audio(source="mic"), [SILENCE])
    assert any("audio:" in line and "source=mic" in line and "fake-capture" in line
               for line in ctx.logs)


async def test_one_colour_per_block(h):
    ctx = await h.run(Audio(), [SILENCE, SILENCE])
    assert len(ctx.device.colors) == 2
    assert h.sources[-1].reads == 3          # two blocks, then end of stream


async def test_stream_end_is_logged_and_ends_the_loop_cleanly(h):
    """The capture dying must not raise out of the mode."""
    ctx = await h.run(Audio(), [SILENCE, SILENCE])
    assert any("capture stream ended" in line for line in ctx.logs)


async def test_capture_is_stopped_when_the_stream_ends(h):
    """No orphaned recorder left holding the audio device."""
    await h.run(Audio(), [SILENCE])
    assert h.sources[-1].stops == 1


async def test_capture_is_stopped_on_cancellation(h):
    """Switching modes cancels this one; the recorder must die with it."""
    ctx = h.ctx([LOUD, SILENCE], then_block=True)
    task = asyncio.ensure_future(Audio().run(ctx))
    for _ in range(500):
        await asyncio.sleep(0)
        if len(ctx.device.colors) >= 2:
            break
    assert ctx.device.colors, "mode never started"
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert h.sources[-1].stops == 1


async def test_capture_is_stopped_when_it_fails_to_start(h):
    """A missing recorder binary surfaces as a mode error, but still cleans up."""
    ctx = h.ctx([], start_error=FileNotFoundError("pw-record"))
    with pytest.raises(FileNotFoundError):
        await Audio().run(ctx)
    assert h.sources[-1].stops == 1


def test_level_of_is_scaled_rms_capped_at_one():
    assert level_of([0.0] * 8) == 0.0
    assert level_of([0.1, -0.1] * 4) == pytest.approx(0.6)
    assert level_of(LOUD) == 1.0
    assert level_of([]) == 0.0


def test_source_is_validated():
    assert Audio(source="mic").source == "mic"
    assert Audio(source="system").source == "system"
    assert Audio(source="nonsense").source == "system"
    assert Audio(source=None).source == "system"


def test_base_rgb_is_coerced_to_ints():
    assert Audio(rgb=["10", 20.9, 30]).base == (10, 20, 30)
    assert Audio(rgb=None).base is None


def test_describe_and_name():
    assert Audio().name == "audio"
    assert "audio" in Audio().describe()
    assert "mic" in Audio(source="mic").describe()
