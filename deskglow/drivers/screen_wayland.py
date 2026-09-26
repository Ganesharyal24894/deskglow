"""ScreenSource for Wayland: portal ScreenCast + `gst-launch-1.0 pipewiresrc`.

The portal hands us a PipeWire fd and node for the monitor the user shared.
A gst-launch child (fd passed via pass_fds) scales each frame down to a small
fixed size and writes raw RGB to stdout; we keep the newest whole frame.
monitors() is the single shared monitor, named "portal".
"""
import asyncio
import contextlib
import os
import shutil

from .portal_screencast import ScreenCastPortal

GST = "gst-launch-1.0"
TOKEN_KEY = "wayland_restore_token"
FRAME_WIDTH = 256
FIRST_FRAME_TIMEOUT = 10.0
MISSING_GST = ("Wayland screen capture needs GStreamer's gst-launch-1.0 and its PipeWire "
               "plugin: install gstreamer1.0-tools and gstreamer1.0-pipewire "
               "(Debian/Ubuntu), or gstreamer1-plugins-base-tools and "
               "gstreamer1-plugin-pipewire / gst-plugin-pipewire (Fedora/Arch)")


def frame_size(src_size, width=FRAME_WIDTH):
    """(w, h) of the scaled frames: `width` wide, source aspect, even height."""
    sw, sh = src_size or (16, 9)
    h = max(2, int(round(width * sh / max(1, sw) / 2)) * 2)
    return width, h


def gst_command(fd, node_id, w, h):
    return [GST, "-q", "pipewiresrc", f"fd={fd}", f"path={node_id}", "!",
            "videoscale", "!", f"video/x-raw,width={w},height={h}", "!",
            "videoconvert", "!", "video/x-raw,format=RGB", "!", "fdsink", "fd=1", "sync=false"]


class FrameSplitter:
    """Cuts a byte stream into fixed-size frames; keeps any partial tail."""

    def __init__(self, frame_bytes):
        self.frame_bytes = frame_bytes
        self._buf = bytearray()

    def feed(self, chunk):
        self._buf += chunk
        n = len(self._buf) // self.frame_bytes
        frames = [bytes(self._buf[i * self.frame_bytes:(i + 1) * self.frame_bytes])
                  for i in range(n)]
        del self._buf[:n * self.frame_bytes]
        return frames


def crop(frame, fw, fh, src, rect):
    """The part of an fw x fh RGB frame covering `rect` (source pixels)."""
    import numpy as np
    arr = np.frombuffer(frame, dtype=np.uint8).reshape(fh, fw, 3)
    sx, sy = fw / src[0], fh / src[1]
    x0, y0 = int(rect["left"] * sx), int(rect["top"] * sy)
    x1 = max(x0 + 1, int((rect["left"] + rect["width"]) * sx))
    y1 = max(y0 + 1, int((rect["top"] + rect["height"]) * sy))
    return arr[max(0, y0):y1, max(0, x0):x1]


class WaylandScreenSource:
    def __init__(self, storage, portal_factory=None, spawn=None, which=shutil.which,
                 width=FRAME_WIDTH):
        self._storage = storage
        self._portal_factory = portal_factory or ScreenCastPortal.connect
        self._spawn = spawn or asyncio.create_subprocess_exec
        self._which = which
        self._width = width
        self._portal = self._proc = self._task = None
        self._latest = None
        self._got = asyncio.Event()
        self._stderr = b""
        self.src = self.size = None

    def _save_token(self, token):
        if token:
            cfg = self._storage.load_config()
            cfg[TOKEN_KEY] = token
            self._storage.save_config(cfg)

    async def _ensure(self):
        if self._proc is not None:
            return
        if not self._which(GST):
            raise RuntimeError(MISSING_GST)
        self._portal = await self._portal_factory()
        stream = await self._portal.open(self._storage.load_config().get(TOKEN_KEY))
        self._save_token(stream.restore_token)    # a new token after every Start
        self.src = stream.size or (1920, 1080)
        self.size = frame_size(self.src, self._width)
        try:
            self._proc = await self._spawn(
                *gst_command(stream.fd, stream.node_id, *self.size),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                pass_fds=(stream.fd,))
        except FileNotFoundError:
            raise RuntimeError(MISSING_GST) from None
        finally:
            with contextlib.suppress(OSError):
                os.close(stream.fd)           # the child holds its own copy
        self._task = asyncio.ensure_future(self._pump())

    async def _pump(self):
        splitter = FrameSplitter(self.size[0] * self.size[1] * 3)
        err = asyncio.ensure_future(self._proc.stderr.read(4096))
        while True:
            chunk = await self._proc.stdout.read(65536)
            if not chunk:
                break
            frames = splitter.feed(chunk)
            if frames:
                self._latest = frames[-1]
                self._got.set()
        with contextlib.suppress(Exception):
            self._stderr = await asyncio.wait_for(err, 1.0)
        self._got.set()                               # wake a waiting grab()

    async def monitors(self):
        await self._ensure()
        return {"portal": {"left": 0, "top": 0, "width": self.src[0], "height": self.src[1]}}

    async def grab(self, rect):
        await self._ensure()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._got.wait(), FIRST_FRAME_TIMEOUT)
        if self._task.done():
            detail = self._stderr.decode(errors="replace").strip()
            hint = (MISSING_GST if b'no element "pipewiresrc"' in self._stderr
                    else "the screen-cast stream stopped")
            self.close()                  # the next grab() opens a fresh session
            raise RuntimeError(f"{hint} ({detail})" if detail else hint)
        if self._latest is None:
            raise RuntimeError("no frame from the screen-cast stream yet")
        return crop(self._latest, *self.size, self.src, rect)

    def close(self):
        """Stop gst, end the portal session. Never raises."""
        task, proc, portal = self._task, self._proc, self._portal
        self._task = self._proc = self._portal = self._latest = None
        self._got = asyncio.Event()
        if task is not None:
            task.cancel()
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.terminate()
        if portal is not None:
            with contextlib.suppress(Exception):
                asyncio.get_running_loop().create_task(portal.close())
