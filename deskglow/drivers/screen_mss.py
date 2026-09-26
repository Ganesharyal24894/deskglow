"""ScreenSource on top of `mss` (X11), with every call on one worker thread.

mss handles are thread-affine, so the handle is created, used and closed on a
single dedicated thread; the async API keeps capture off the event loop.
"""
import asyncio
import concurrent.futures

from . import x11_display


class MssScreenSource:
    def __init__(self, list_monitors=None, mss_factory=None):
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._list_monitors = list_monitors or x11_display.get_monitors
        self._mss_factory = mss_factory
        self._sct = None

    def _ensure(self):
        if self._sct is None:
            if self._mss_factory is None:
                import mss
                self._mss_factory = mss.mss
            self._sct = self._mss_factory()
        return self._sct

    def _grab_sync(self, rect):
        import numpy as np
        img = self._ensure().grab(rect)
        return np.frombuffer(img.rgb, dtype=np.uint8).reshape(img.height, img.width, 3)

    def _close_sync(self):
        sct, self._sct = self._sct, None
        if sct is not None:
            try:
                sct.close()
            except Exception:
                pass

    async def _call(self, func, *args):
        return await asyncio.get_running_loop().run_in_executor(self._pool, func, *args)

    async def monitors(self):
        return await self._call(self._list_monitors)

    async def grab(self, rect):
        return await self._call(self._grab_sync, rect)

    def close(self):
        """Close the handle on its own thread, then let the thread go."""
        try:
            self._pool.submit(self._close_sync)
        except RuntimeError:     # already shut down
            pass
        self._pool.shutdown(wait=False)
