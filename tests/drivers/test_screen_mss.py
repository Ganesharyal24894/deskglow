"""MssScreenSource: grabs on ONE worker thread, as uint8 RGB arrays.

mss is never imported: the driver gets an injected mss factory and monitor
lister, which record the thread each call ran on.
"""
import threading
import time

import numpy as np

from deskglow.drivers.screen_mss import MssScreenSource

RECT = {"left": 0, "top": 0, "width": 4, "height": 2}


class FakeImg:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.rgb = bytes(range(width * height * 3))


class FakeSct:
    def __init__(self, log):
        self.log = log
        self.closed = 0
        log.append(("create", threading.get_ident()))

    def grab(self, rect):
        self.log.append(("grab", threading.get_ident()))
        return FakeImg(rect["width"], rect["height"])

    def close(self):
        self.closed += 1
        self.log.append(("close", threading.get_ident()))


def make():
    log, handles = [], []

    def factory():
        sct = FakeSct(log)
        handles.append(sct)
        return sct

    def monitors():
        log.append(("monitors", threading.get_ident()))
        return {"X": dict(RECT)}

    return MssScreenSource(list_monitors=monitors, mss_factory=factory), log, handles


def _wait_for(pred, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.005)
    return pred()


async def test_grab_returns_an_hxwx3_uint8_rgb_array():
    src, _log, _h = make()
    try:
        arr = await src.grab(RECT)
        assert isinstance(arr, np.ndarray) and arr.dtype == np.uint8
        assert arr.shape == (2, 4, 3)
        assert arr[0, 1].tolist() == [3, 4, 5], "pixels must keep mss's RGB order"
    finally:
        src.close()


async def test_monitors_come_from_the_lister():
    src, _log, _h = make()
    try:
        assert await src.monitors() == {"X": RECT}
    finally:
        src.close()


async def test_every_call_runs_on_one_worker_thread():
    """mss handles are thread-affine: create, grab and close share a thread,
    and that thread is not the event loop's."""
    src, log, handles = make()
    await src.monitors()
    await src.grab(RECT)
    await src.grab(RECT)
    src.close()
    assert _wait_for(lambda: handles and handles[0].closed == 1)
    threads = {tid for _what, tid in log}
    assert len(threads) == 1
    assert threading.get_ident() not in threads
    assert [w for w, _ in log] == ["monitors", "create", "grab", "grab", "close"]


async def test_the_handle_is_created_once_and_reused():
    src, _log, handles = make()
    await src.grab(RECT)
    await src.grab(RECT)
    src.close()
    assert len(handles) == 1


async def test_close_is_safe_twice_and_without_a_grab():
    src, _log, handles = make()
    src.close()
    src.close()
    assert handles == []
    src2, _log2, handles2 = make()
    await src2.grab(RECT)
    src2.close()
    src2.close()
    assert _wait_for(lambda: handles2[0].closed == 1)
    time.sleep(0.02)
    assert handles2[0].closed == 1
