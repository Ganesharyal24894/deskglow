"""PipeWire driver: the pw-record capture process, its blocks, and cleanup.

No pw-record is ever spawned: asyncio.create_subprocess_exec is replaced in the
driver module with a fake serving synthetic int16 PCM through a fake stdout.
"""
import asyncio

import numpy as np
import pytest

from deskglow.drivers import audio_pipewire as pw

BLOCK = 1024


class FakeStdout:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.requested = []

    async def readexactly(self, n):
        self.requested.append(n)
        if self.chunks:
            return self.chunks.pop(0)
        raise asyncio.IncompleteReadError(b"", n)


class FakeProc:
    def __init__(self, stdout):
        self.stdout = stdout
        self.terminated = 0
        self.waited = 0

    def terminate(self):
        self.terminated += 1

    async def wait(self):
        self.waited += 1
        return 0


class _FakeAsyncio:
    def __init__(self):
        self.cmds = []
        self.kwargs = []
        self.procs = []
        self.chunks = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def create_subprocess_exec(self, *cmd, **kw):
        self.cmds.append(list(cmd))
        self.kwargs.append(kw)
        proc = FakeProc(FakeStdout(self.chunks))
        self.procs.append(proc)
        return proc


@pytest.fixture
def fake(monkeypatch):
    shim = _FakeAsyncio()
    monkeypatch.setattr(pw, "asyncio", shim)
    return shim


def source():
    return pw.PipeWireAudioSource(sink_lookup=lambda: "fake.sink")


# ------------------------------------------------------------ the command ---

async def test_captures_the_default_sink_monitor_for_system_audio(fake):
    """"system" means: record what the speakers are playing."""
    desc = await source().start("system", None, 22050, BLOCK)
    cmd = fake.cmds[0]
    assert cmd[0] == "pw-record"
    assert cmd[cmd.index("--rate") + 1] == "22050"
    assert cmd[cmd.index("--channels") + 1] == "1"
    assert cmd[cmd.index("--format") + 1] == "s16"
    assert cmd[cmd.index("--target") + 1] == "fake.sink"
    assert cmd[-1] == "-", "audio must be streamed to stdout"
    assert fake.kwargs[0]["stdout"] is asyncio.subprocess.PIPE
    assert desc == " ".join(cmd), "the description names the exact command"


async def test_mic_source_captures_the_default_input(fake):
    """"mic" takes pw-record's default input, so no --target is passed."""
    await source().start("mic", None, 22050, BLOCK)
    assert "--target" not in fake.cmds[0]


@pytest.mark.parametrize("kind", ["system", "mic"])
async def test_explicit_target_wins(fake, kind):
    await source().start(kind, "my.sink.monitor", 22050, BLOCK)
    cmd = fake.cmds[0]
    assert cmd[cmd.index("--target") + 1] == "my.sink.monitor"


async def test_system_without_a_known_sink_records_the_default(fake):
    """No sink found (pw-dump missing) still captures something, untargeted."""
    await pw.PipeWireAudioSource(sink_lookup=lambda: None).start("system", None, 8000, BLOCK)
    assert "--target" not in fake.cmds[0]


# ------------------------------------------------------------------ blocks ---

async def test_reads_fixed_size_blocks_as_floats(fake):
    """int16 mono: `block` samples is block*2 bytes, scaled to -1..1."""
    samples = np.array([0, 16384, -32768, 32767] * (BLOCK // 4), dtype=np.int16)
    fake.chunks = [samples.tobytes()]
    src = source()
    await src.start("system", None, 22050, BLOCK)
    block = await src.read()
    assert fake.procs[0].stdout.requested == [BLOCK * 2]
    assert len(block) == BLOCK
    assert list(block[:4]) == pytest.approx([0.0, 0.5, -1.0, 32767 / 32768])


async def test_end_of_stream_reads_as_none(fake):
    """pw-record dying is an end of stream, not an IncompleteReadError."""
    src = source()
    await src.start("system", None, 22050, BLOCK)
    assert await src.read() is None


# ------------------------------------------------------------------- stop ----

async def test_stop_terminates_and_reaps_the_process(fake):
    """No orphaned pw-record left holding the audio device."""
    src = source()
    await src.start("system", None, 22050, BLOCK)
    await src.stop()
    assert fake.procs[0].terminated == 1
    assert fake.procs[0].waited == 1


async def test_stop_is_safe_twice_and_before_start(fake):
    src = source()
    await src.stop()
    await src.start("system", None, 22050, BLOCK)
    await src.stop()
    await src.stop()
    assert fake.procs[0].terminated == 1


async def test_stop_survives_a_process_that_already_exited(fake):
    src = source()
    await src.start("system", None, 22050, BLOCK)

    def gone():
        raise ProcessLookupError()

    fake.procs[0].terminate = gone
    await src.stop()          # must not raise
