"""drivers.audio_soundcard with a fake `soundcard` module: device choice per
OS, the recording thread feeding the async API, and cleanup."""
import threading

import numpy as np
import pytest

from deskglow.drivers import audio_soundcard as asc


class FakeRecorder:
    def __init__(self, mic, block, fail=None):
        self.mic, self.block, self.fail = mic, block, fail
        self.n = 0

    def __enter__(self):
        self.mic.threads.append(threading.get_ident())
        return self

    def __exit__(self, *exc):
        self.mic.closed += 1
        return False

    def record(self, numframes):
        if self.fail:
            raise self.fail
        self.n += 1
        self.mic.sleep()
        return np.full((numframes, 1), self.n / 100, dtype=np.float32)


class FakeMic:
    def __init__(self, name, fail=None):
        self.name, self.fail = name, fail
        self.threads, self.closed, self.opened = [], 0, []
        self.sleep = lambda: threading.Event().wait(0.002)

    def recorder(self, samplerate, channels, blocksize):
        self.opened.append((samplerate, channels, blocksize))
        return FakeRecorder(self, blocksize, self.fail)


class FakeSoundcard:
    def __init__(self, fail=None):
        self.speaker = type("Spk", (), {"name": "Speakers (Realtek)"})()
        self.mic = FakeMic("Microphone", fail)
        self.loopbacks = []

    def default_speaker(self):
        return self.speaker

    def default_microphone(self):
        return self.mic

    def get_microphone(self, name, include_loopback=False):
        assert include_loopback
        if name == "nope":
            raise IndexError("no microphone with id nope")
        self.loopbacks.append(name)
        return FakeMic(name)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_system_is_a_loopback_of_the_default_speaker(platform):
    sc = FakeSoundcard()
    mic, desc = asc.pick_microphone(sc, "system", None, platform)
    assert sc.loopbacks == ["Speakers (Realtek)"] and mic.name == "Speakers (Realtek)"
    assert "loopback" in desc


def test_mic_is_the_default_microphone_everywhere():
    sc = FakeSoundcard()
    for platform in ("win32", "darwin", "linux"):
        assert asc.pick_microphone(sc, "mic", None, platform)[0] is sc.mic


def test_macos_system_audio_explains_blackhole():
    with pytest.raises(RuntimeError, match="BlackHole"):
        asc.pick_microphone(FakeSoundcard(), "system", None, "darwin")


def test_an_explicit_target_wins_even_on_macos():
    sc = FakeSoundcard()
    mic, _ = asc.pick_microphone(sc, "system", "BlackHole 2ch", "darwin")
    assert mic.name == "BlackHole 2ch"


def test_an_unknown_target_is_a_clear_error():
    with pytest.raises(RuntimeError, match="no matching audio device"):
        asc.pick_microphone(FakeSoundcard(), "mic", "nope", "win32")


async def test_blocks_arrive_as_mono_floats_recorded_off_the_event_loop():
    sc = FakeSoundcard()
    com = []
    src = asc.SoundcardAudioSource(platform="win32", soundcard=sc,
                                   com_init=lambda: com.append("init") or (lambda: com.append("un")))
    desc = await src.start("mic", None, 44100, 512)
    assert "Microphone" in desc
    first = await src.read()
    assert first.shape == (512,) and first.dtype == np.float32
    await src.read()
    await src.stop()
    assert sc.mic.opened == [(44100, 1, 512)]
    assert sc.mic.threads and sc.mic.threads[0] != threading.get_ident()
    assert sc.mic.closed == 1, "recorder not released"
    assert com == ["init", "un"], "COM must be set up and torn down on the recording thread"
    await src.stop()                       # twice: fine


async def test_a_recording_error_surfaces_then_the_stream_ends():
    src = asc.SoundcardAudioSource(platform="linux", soundcard=FakeSoundcard(fail=OSError("gone")))
    await src.start("mic", None, 48000, 256)
    with pytest.raises(RuntimeError, match="audio capture failed: gone"):
        await src.read()
    assert await src.read() is None
    assert await src.read() is None
    await src.stop()


async def test_a_slow_reader_gets_recent_blocks_not_a_growing_backlog():
    sc = FakeSoundcard()
    sc.mic.sleep = lambda: None                # record as fast as possible
    src = asc.SoundcardAudioSource(platform="linux", soundcard=sc)
    await src.start("mic", None, 8000, 16)
    import asyncio
    await asyncio.sleep(0.05)
    assert src._queue.qsize() <= asc.QUEUE_BLOCKS
    await src.stop()


async def test_read_before_start_is_end_of_stream():
    assert await asc.SoundcardAudioSource(platform="linux", soundcard=FakeSoundcard()).read() is None


def test_linux_prefers_pipewire_and_falls_back_to_soundcard():
    from deskglow.drivers.audio_pipewire import PipeWireAudioSource
    assert isinstance(asc.linux_audio_source(lambda n: "/usr/bin/pw-record"), PipeWireAudioSource)
    fallback = asc.linux_audio_source(lambda n: None)
    assert isinstance(fallback, asc.SoundcardAudioSource) and fallback._com_init is None
