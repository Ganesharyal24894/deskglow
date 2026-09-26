"""Mode lifecycle for the daemon: one mode at a time, atomically switched.

Speaker-friendly: while the mode is 'off' the daemon releases the BLE link after
a short idle timeout, so the radio behaves as if the strip weren't connected.
"""
import asyncio
import contextlib

from ..model.settings import IDLE_DISCONNECT, validate_setting
from . import modes

WATCHDOG_PERIOD = 60.0
WATCHDOG_FAILURES = 40    # consecutive connect failures before recycling
REAP_ATTEMPTS = 30


class ModeLifecycle:
    """Expects: self.device, self.state, self.settings, self.services, self.log."""

    def _init_lifecycle(self):
        self.mode_task = None
        self.mode_name = "off"
        self.mode_desc = "off"
        self.mode_args = {}
        self.mode_ctx = None   # the running mode's ModeContext (for status)
        self._idle_task = None
        self._stop = asyncio.Event()
        # Mode transitions must be atomic: commands arrive on independent
        # connections (each served by its own task), so two overlapping
        # set_mode() calls could otherwise each start a mode and leave the
        # loser's task running unreferenced -> two modes driving the strip at
        # once (visible as the colour flickering between them).
        self._mode_lock = asyncio.Lock()
        self._gen = 0          # bumped on every transition; stale modes bail out
        self._orphans = set()  # tasks that ignored cancel(), reaped in background
        # asyncio keeps only weak references to running tasks, so a
        # fire-and-forget create_task() can be garbage collected mid-flight.
        # Every background task we start is held here until it finishes.
        self._bg_tasks = set()

    async def _run_mode(self, mode, gen):
        ctx = modes.ModeContext(self.device, self.state, self.log,
                                is_current=lambda: gen == self._gen,
                                services=self.services)
        if gen == self._gen:
            self.mode_ctx = ctx
        try:
            await mode.run(ctx)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a mode crashing must not kill the daemon
            self.log(f"mode {mode.name} error: {type(e).__name__}: {e}")
            self.mode_name = "off"
            self.mode_desc = f"off (after {mode.name} error)"

    async def _stop_mode(self):
        """Cancel the running mode and make sure it is really gone.

        Never drop the reference to a task that hasn't finished: an unreferenced
        mode loop keeps writing colours and fights the new mode. If it doesn't
        stop promptly (it may be blocked in a slow BLE op) it is reaped in the
        background instead, and the generation bump stops it writing meanwhile.
        """
        task, self.mode_task = self.mode_task, None
        if task is None or task.done():
            return
        task.cancel()
        _done, pending = await asyncio.wait({task}, timeout=5.0)
        if pending:
            self.log("mode task slow to stop; reaping in background")
            self._orphans.add(task)
            self._spawn_bg(self._reap(task))

    async def _reap(self, task):
        """Keep cancelling a stubborn mode task until it actually exits."""
        try:
            for _ in range(REAP_ATTEMPTS):
                if task.done():
                    return
                task.cancel()
                await asyncio.sleep(1.0)
            self.log("mode task still alive after reaping; exiting for a clean restart")
            self.services.process.exit_for_restart(1)
        finally:
            self._orphans.discard(task)

    def _spawn_bg(self, coro):
        """Start a background task and keep a strong reference to it."""
        task = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    def start_background_tasks(self):
        """Start the long-lived helpers: the watchdog and the sunset timer."""
        self._spawn_bg(self._watchdog())
        self._spawn_bg(self.sunset.run())

    async def shutdown_background_tasks(self):
        """Cancel every helper task so none outlives the event loop."""
        self._cancel_idle()
        tasks = list(self._bg_tasks) + list(self._orphans)
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._bg_tasks.clear()
        self._orphans.clear()

    def _cancel_idle(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

    async def _watchdog(self):
        """Safety net: if the strip is unreachable for a very long stretch, exit
        so the service manager restarts us fresh — this frees any leaked
        D-Bus/socket FDs before they could approach the per-user bus limit."""
        while not self._stop.is_set():
            await asyncio.sleep(WATCHDOG_PERIOD)
            # only recycle for a *real* connectivity problem, not because the
            # strip simply isn't configured yet
            if self.device.address and self.device.consecutive_failures >= WATCHDOG_FAILURES:
                self.log(f"persistent connect failures "
                         f"(x{self.device.consecutive_failures}); exiting for a clean "
                         f"restart to release resources")
                self.services.process.exit_for_restart(1)

    async def _idle_then_disconnect(self):
        try:
            await asyncio.sleep(IDLE_DISCONNECT)
            if self.mode_name == "off":
                await self.device.disconnect()
        except asyncio.CancelledError:
            pass

    async def set_mode(self, name, args):
        async with self._mode_lock:
            await self._set_mode(name, args)

    async def _set_mode(self, name, args):
        """Switch modes. Caller must hold self._mode_lock."""
        self._gen += 1          # supersede the outgoing mode before anything awaits
        self._cancel_idle()
        await self._stop_mode()
        args = args or {}
        self.mode_ctx = None
        self._remember(name, args)
        if name == "off":
            self.mode_name = self.mode_desc = "off"
            self.mode_args = {}
            with contextlib.suppress(Exception):
                await self.device.power(False)
            self._idle_task = asyncio.ensure_future(self._idle_then_disconnect())
            self._persist()
            return
        if name == "screen" and args.get("style"):
            try:
                self.state["screen_style"] = validate_setting("screen_style", args["style"])
                self.settings.save_state(self.state)
            except ValueError as e:
                self.log(f"ignoring bad screen style: {e}")
        try:
            mode = modes.build(name, args, preset=self.services.preset)
        except Exception as e:
            self.log(f"cannot start mode {name!r} ({e}); staying off")
            self.mode_name = "off"
            self.mode_desc = f"off (bad {name})"
            self.mode_args = {}
            self._persist()
            return
        # Publish the new mode before the (possibly slow) power-on, so `status`
        # reports what the daemon is starting instead of claiming to be off.
        self.mode_name = name
        self.mode_desc = mode.describe()
        self.mode_args = args
        self._persist()
        # A prior `off` powered the strip down; if the link is still open the
        # per-connect power-on won't fire, so explicitly power on before the mode
        # starts sending colors (otherwise color writes are ignored while off).
        with contextlib.suppress(Exception):
            await self.device.power(True)
        self.mode_task = asyncio.create_task(self._run_mode(mode, self._gen))

    def _persist(self):
        self.state["mode"] = self.mode_name
        self.state["args"] = self.mode_args   # so args-bearing modes restore too
        with contextlib.suppress(Exception):
            self.settings.save_state(self.state)
