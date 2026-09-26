"""AudioSource on `soundcard` (Windows WASAPI, macOS CoreAudio, PulseAudio).

soundcard's recorder blocks, so it runs on a dedicated thread that hands
blocks to the event loop through a small queue (oldest dropped if the mode
falls behind). "system" is a loopback of the default speaker; macOS has no
loopback without a virtual device such as BlackHole.
"""
import asyncio
import shutil
import sys
import threading

QUEUE_BLOCKS = 8
MAC_NO_LOOPBACK = ("macOS cannot record system audio by itself. Install a loopback "
                   "device such as BlackHole, route your output through it, and pick "
                   "it as the audio target (or use --source mic).")


def _soundcard():
    import soundcard
    return soundcard


def pick_microphone(sc, source, target, platform):
    """(recording device, description) for source/target on `platform`."""
    try:
        if target:
            mic = sc.get_microphone(target, include_loopback=True)
            return mic, f"soundcard device {mic.name!r}"
        if source == "mic":
            mic = sc.default_microphone()
            return mic, f"default microphone {mic.name!r}"
        if platform == "darwin":
            raise RuntimeError(MAC_NO_LOOPBACK)
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.name, include_loopback=True)
        return mic, f"loopback of {speaker.name!r}"
    except (IndexError, KeyError, ValueError) as e:
        raise RuntimeError(f"no matching audio device ({e})") from e


def _windows_com_init():
    """WASAPI calls need COM on the recording thread (multithreaded apartment)."""
    import ctypes
    ole32 = ctypes.windll.ole32
    ole32.CoInitializeEx(None, 0)       # COINIT_MULTITHREADED
    return ole32.CoUninitialize


class SoundcardAudioSource:
    def __init__(self, platform=None, soundcard=None, com_init=None):
        self._platform = sys.platform if platform is None else platform
        self._sc = soundcard
        self._com_init = com_init or (_windows_com_init if self._platform == "win32" else None)
        self._queue = self._thread = None
        self._stop = threading.Event()

    async def start(self, source, target, rate, block):
        mic, desc = pick_microphone(self._sc or _soundcard(), source, target, self._platform)
        loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._record,
                                        args=(mic, rate, block, loop, self._queue, self._stop),
                                        name="deskglow-audio", daemon=True)
        self._thread.start()
        return desc

    @staticmethod
    def _put(queue, item):
        if queue.qsize() >= QUEUE_BLOCKS:
            queue.get_nowait()                # drop the oldest: stay live
        queue.put_nowait(item)

    def _record(self, mic, rate, block, loop, queue, stop):
        uninit = None
        try:
            if self._com_init is not None:
                uninit = self._com_init()
            with mic.recorder(samplerate=rate, channels=1, blocksize=block) as rec:
                while not stop.is_set():
                    data = rec.record(numframes=block)
                    mono = data[:, 0] if getattr(data, "ndim", 1) == 2 else data
                    loop.call_soon_threadsafe(self._put, queue, mono)
        except Exception as e:
            loop.call_soon_threadsafe(self._put, queue, e)
        finally:
            if uninit is not None:
                try:
                    uninit()
                except Exception:
                    pass
            try:
                loop.call_soon_threadsafe(self._put, queue, None)
            except RuntimeError:              # loop already closed
                pass

    async def read(self):
        if self._queue is None:
            return None
        item = await self._queue.get()
        if item is None:
            self._queue = None                # ended: later reads return None too
        if isinstance(item, Exception):
            raise RuntimeError(f"audio capture failed: {item}") from item
        return item

    async def stop(self):
        thread, self._thread = self._thread, None
        self._stop.set()
        if thread is not None:
            await asyncio.get_running_loop().run_in_executor(None, thread.join, 2.0)


def linux_audio_source(which=shutil.which):
    """PipeWire's pw-record when present, else soundcard (PulseAudio)."""
    if which("pw-record"):
        from .audio_pipewire import PipeWireAudioSource
        return PipeWireAudioSource()
    return SoundcardAudioSource(platform="linux")
