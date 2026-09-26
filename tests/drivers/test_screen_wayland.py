"""drivers.screen_wayland: frame parsing and the portal -> gst-launch flow,
with a fake portal and a fake gst process (no Wayland, no PipeWire, no gst)."""
import asyncio
import os

import numpy as np
import pytest
from fakes import FakeStorage

from deskglow.drivers import screen_wayland as sw
from deskglow.drivers.portal_screencast import PortalStream


def test_frame_size_keeps_the_aspect_with_an_even_height():
    assert sw.frame_size((2560, 1440), 256) == (256, 144)
    assert sw.frame_size((1366, 768), 256) == (256, 144)
    assert sw.frame_size((1000, 1), 256) == (256, 2)
    assert sw.frame_size(None, 160) == (160, 90)


def test_gst_command_reads_the_portal_node_and_writes_raw_rgb_to_stdout():
    cmd = sw.gst_command(7, 57, 256, 144)
    assert cmd[:2] == ["gst-launch-1.0", "-q"], "-q: no chatter mixed into the frames"
    assert cmd[2:5] == ["pipewiresrc", "fd=7", "path=57"]
    text = " ".join(cmd)
    assert "videoscale ! video/x-raw,width=256,height=144 ! videoconvert" in text
    assert text.endswith("video/x-raw,format=RGB ! fdsink fd=1 sync=false")


def test_frame_splitter_cuts_fixed_frames_across_arbitrary_chunks():
    s = sw.FrameSplitter(6)
    assert s.feed(b"abcd") == []
    assert s.feed(b"efghijklm") == [b"abcdef", b"ghijkl"]
    assert s.feed(b"nopqr") == [b"mnopqr"]
    assert s.feed(b"") == []


def test_crop_maps_source_pixels_onto_the_scaled_frame():
    frame = bytes(np.arange(4 * 2 * 3, dtype=np.uint8))       # 4x2 RGB
    whole = sw.crop(frame, 4, 2, (400, 200), {"left": 0, "top": 0, "width": 400, "height": 200})
    assert whole.shape == (2, 4, 3) and whole.dtype == np.uint8
    right = sw.crop(frame, 4, 2, (400, 200), {"left": 200, "top": 100, "width": 200, "height": 100})
    assert right.shape == (1, 2, 3)
    assert right.tolist() == whole[1:, 2:].tolist()


class FakePortal:
    def __init__(self, stream):
        self.stream, self.opened, self.closed = stream, [], 0

    async def open(self, token):
        self.opened.append(token)
        return self.stream

    async def close(self):
        self.closed += 1


class FakeProc:
    def __init__(self, data, stderr=b""):
        self.stdout, self.stderr = asyncio.StreamReader(), asyncio.StreamReader()
        self.stdout.feed_data(data)
        self.stderr.feed_data(stderr)
        self.terminated = 0

    def end(self):
        self.stdout.feed_eof()
        self.stderr.feed_eof()

    def terminate(self):
        self.terminated += 1


def make(data=b"", stderr=b"", which=lambda n: "/usr/bin/" + n, config=None):
    r, w = os.pipe()                   # a real fd the driver must close
    os.close(w)
    portal = FakePortal(PortalStream(r, 57, (400, 200), "new-token"))
    procs, spawned = [], []

    async def spawn(*cmd, **kw):
        spawned.append((cmd, kw))
        procs.append(FakeProc(data, stderr))
        return procs[-1]

    async def portal_factory():
        return portal

    storage = FakeStorage(config=config or {"address": "A", sw.TOKEN_KEY: "old-token"})
    src = sw.WaylandScreenSource(storage, portal_factory=portal_factory, spawn=spawn,
                                 which=which, width=4)
    return src, portal, procs, spawned, storage, r


async def test_monitors_is_the_single_portal_monitor_and_tokens_round_trip():
    src, portal, _procs, spawned, storage, fd = make()
    assert await src.monitors() == {"portal": {"left": 0, "top": 0, "width": 400, "height": 200}}
    assert portal.opened == ["old-token"]
    assert storage.config == {"address": "A", sw.TOKEN_KEY: "new-token"}, \
        "the new restore token must be saved (and the rest of the config kept)"
    cmd, kw = spawned[0]
    assert list(cmd) == sw.gst_command(fd, 57, 4, 2)
    assert kw["pass_fds"] == (fd,)
    with pytest.raises(OSError):
        os.fstat(fd)                   # parent's copy closed after the spawn
    await src.monitors()
    assert len(spawned) == 1, "a second monitors() re-opened the portal"
    src.close()


async def test_grab_returns_the_newest_complete_frame_cropped():
    f1, f2 = bytes([1] * 24), bytes([2] * 24)
    src, *_ = make(data=f1 + f2 + b"\x09" * 5)     # two frames + a partial one
    img = await src.grab({"left": 0, "top": 0, "width": 400, "height": 200})
    assert img.shape == (2, 4, 3)
    assert set(img.flatten().tolist()) == {2}
    src.close()


async def test_missing_gst_launch_names_the_packages():
    src, portal, *_ = make(which=lambda n: None)
    with pytest.raises(RuntimeError, match="gstreamer1.0-tools.*gstreamer1.0-pipewire"):
        await src.monitors()
    assert portal.opened == [], "asked the user to share a screen we cannot read"


async def test_missing_pipewire_plugin_is_reported_with_the_packages():
    src, _portal, procs, *_ = make(stderr=b'WARNING: erroneous pipeline: no element "pipewiresrc"')
    await src.monitors()
    procs[0].end()
    with pytest.raises(RuntimeError, match="gst-plugin-pipewire"):
        await src.grab({"left": 0, "top": 0, "width": 400, "height": 200})


async def test_a_stopped_stream_errors_then_the_next_grab_reopens():
    src, portal, procs, spawned, *_ = make()
    await src.monitors()
    procs[0].end()
    with pytest.raises(RuntimeError, match="stream stopped"):
        await src.grab({"left": 0, "top": 0, "width": 400, "height": 200})
    assert procs[0].terminated == 1
    await asyncio.sleep(0)             # let the scheduled portal.close() run
    assert portal.closed == 1
    await src.monitors()
    assert len(spawned) == 2


async def test_close_stops_gst_and_ends_the_portal_session():
    src, portal, procs, *_ = make()
    await src.monitors()
    src.close()
    await asyncio.sleep(0)
    assert procs[0].terminated == 1 and portal.closed == 1
    src.close()                        # twice: never raises
