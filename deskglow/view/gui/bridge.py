"""Talk to the daemon without ever blocking the Qt thread.

A worker thread runs its own asyncio loop; every request (and any blocking call
such as toggling start-at-login) runs there. Results come back to the Qt thread
through a queued signal, where the caller's callback runs. The app never uses
Bluetooth itself: everything goes through DaemonClient requests.
"""
import asyncio
import itertools
import logging
import threading

from PySide6.QtCore import QObject, Signal, Slot

log = logging.getLogger("deskglow.gui")


def failure(message):
    return {"ok": False, "error": message}


class ThreadBridge(QObject):
    # emitted from the worker thread; Qt queues it onto the receiver's thread
    _finished = Signal(int, object)

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self._callbacks = {}
        self._ids = itertools.count(1)
        self._ready = False
        self._stopped = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="deskglow-bridge", daemon=True)
        self._finished.connect(self._deliver)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # ---- API (Qt thread) ---------------------------------------------------

    def request(self, req, callback=None, timeout=25.0):
        """Send `req` to the daemon; `callback(reply)` runs on the Qt thread.
        The reply is always a dict; failures are {"ok": False, "error": ...}."""
        return self._submit(self._request(req, timeout), callback)

    def call(self, fn, callback=None):
        """Run blocking `fn()` on the worker; `callback(result)` on the Qt thread.
        An exception becomes the result (callers check isinstance)."""
        return self._submit(self._call(fn), callback)

    def stop(self):
        """Cancel whatever is in flight, stop the worker, close its loop."""
        if self._stopped:
            return
        self._stopped = True
        if self._thread.is_alive():
            fut = asyncio.run_coroutine_threadsafe(self._cancel_all(), self._loop)
            try:
                fut.result(timeout=2.0)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
        if not self._loop.is_running():
            self._loop.close()

    @staticmethod
    async def _cancel_all():
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    # ---- worker side ---------------------------------------------------------

    def _submit(self, coro, callback):
        if self._stopped:
            coro.close()               # shutting down: nothing will run it
            return None
        rid = next(self._ids)
        self._callbacks[rid] = callback
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        fut.add_done_callback(lambda f: self._finished.emit(rid, self._outcome(f)))
        return rid

    @staticmethod
    def _outcome(fut):
        try:
            return fut.result()
        except BaseException as e:   # cancelled at shutdown, or a bug
            return failure(f"{type(e).__name__}: {e}")

    async def _request(self, req, timeout):
        try:
            if not self._ready:
                if not await self.client.ensure_daemon():
                    return failure("the Deskglow service is not running")
                self._ready = True
            reply = await self.client.request(req, timeout=timeout)
        except Exception as e:
            self._ready = False        # re-check (and maybe start) the daemon next time
            return failure(f"{type(e).__name__}: {e}")
        if not isinstance(reply, dict):
            self._ready = False
            return failure("no response from the Deskglow service")
        return reply

    async def _call(self, fn):
        try:
            return fn()
        except Exception as e:
            return e

    @Slot(int, object)
    def _deliver(self, rid, result):
        callback = self._callbacks.pop(rid, None)
        if callback is None:
            return
        try:
            callback(result)
        except Exception:
            log.exception("GUI callback failed")
