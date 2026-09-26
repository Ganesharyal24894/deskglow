"""Fakes for the audio-mode tests: a scripted AudioSource and a virtual clock."""
import asyncio

import numpy as np
from fakes import make_services

from deskglow.controller.modes import audio as audio_mod
from deskglow.controller.modes import base as base_mod
from deskglow.controller.modes.audio import CHUNK


def pcm(amplitude, samples=CHUNK):
    """`samples` float samples (-1..1) of a sine at the given 0..1 amplitude,
    quantised through int16 exactly as a 16-bit capture would be."""
    t = np.arange(samples, dtype=np.float64)
    sig = (np.sin(2 * np.pi * t / 64.0) * amplitude * 32767.0).astype(np.int16)
    return sig.astype(np.float32) / 32768.0


SILENCE = pcm(0.0)
LOUD = pcm(1.0)
QUIET = pcm(0.05)


class FakeAudioSource:
    def __init__(self, blocks, then_block=False, start_error=None):
        self.blocks = list(blocks)
        self.then_block = then_block
        self.start_error = start_error
        self.started = []         # [(source, target, rate, block)]
        self.reads = 0
        self.stops = 0

    async def start(self, source, target, rate, block):
        self.started.append((source, target, rate, block))
        if self.start_error is not None:
            raise self.start_error
        return f"fake-capture --rate {rate}"

    async def read(self):
        self.reads += 1
        if self.blocks:
            return self.blocks.pop(0)
        if self.then_block:
            await asyncio.Event().wait()      # never resolves; the test cancels
        return None

    async def stop(self):
        self.stops += 1


class _Clock:
    """loop.time() that advances one second per call, so the hue drift that
    depends on wall-clock time is observable without waiting for it."""

    def __init__(self, start=1000.0, step=1.0):
        self.now = start
        self.step = step

    def time(self):
        now = self.now
        self.now += self.step
        return now


class _FakeAsyncio:
    def __init__(self):
        self._clock = _Clock()

    def __getattr__(self, name):
        return getattr(asyncio, name)

    def get_event_loop(self):
        return self._clock

    async def sleep(self, delay, result=None):
        await asyncio.sleep(0)
        return result


class Harness:
    """Builds contexts whose audio factory hands out FakeAudioSources."""

    def __init__(self, make_ctx):
        self.make_ctx = make_ctx
        self.sources = []

    def ctx(self, blocks=(), state=None, **source_kw):
        def factory():
            src = FakeAudioSource(blocks, **source_kw)
            self.sources.append(src)
            return src
        return self.make_ctx(state=state, services=make_services(audio=factory))

    async def run(self, mode, blocks, state=None):
        """Run the mode over a finite stream; it returns when read() gives None."""
        ctx = self.ctx(blocks, state)
        await asyncio.wait_for(mode.run(ctx), 5.0)
        return ctx


def install(monkeypatch, make_ctx):
    shim = _FakeAsyncio()
    monkeypatch.setattr(audio_mod, "asyncio", shim)
    monkeypatch.setattr(base_mod, "asyncio", shim)
    return Harness(make_ctx)
