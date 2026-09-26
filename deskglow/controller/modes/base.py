"""Mode base class and the context modes use to drive the strip."""
import asyncio


def _ceiling(value):
    """The brightness ceiling as a 0..1 factor.

    Defensive on purpose: a state file written by an older version (or by hand)
    must never take the running mode down with a TypeError.
    """
    try:
        return max(0.0, min(1.0, float(value) / 100.0))
    except (TypeError, ValueError):
        return 1.0


class ModeContext:
    """Everything a mode needs: a way to set color, shared state, and the
    services (encoder, screen/focus/audio factories) the app wired in.

    set() never raises: a BLE outage is swallowed and self-throttled, so a mode
    keeps running (and resumes the moment the strip is reachable again) instead
    of dying or busy-looping.
    """

    def __init__(self, device, state, logger, is_current=None, services=None):
        self.device = device
        self.state = state
        self.log = logger
        self.services = services
        # What the mode is showing (before any brightness scaling), and live
        # readings a mode publishes for `status` (screen colour/fps, audio
        # level, focus timer). `controls` carries requests back to the mode.
        self.shown = None
        self.telemetry = {}
        self.controls = {}
        self._fails = 0
        # The daemon supersedes a mode by bumping its generation counter. A mode
        # that is no longer current must not touch the strip: if it somehow
        # outlived its cancel() (e.g. it was blocked in a slow BLE call), its
        # writes would fight the new mode's and the strip would flicker between
        # the two colours.
        self._is_current = is_current or (lambda: True)

    def _check_current(self):
        if not self._is_current():
            raise asyncio.CancelledError("mode superseded")

    async def _guard(self, coro):
        """Await a device call, swallowing+throttling errors so a mode never
        dies or busy-loops while the strip is unreachable."""
        try:
            await coro
            if self._fails:
                self.log("strip reachable again")
            self._fails = 0
        except Exception as e:
            self._fails += 1
            if self._fails == 1 or self._fails % 50 == 0:
                self.log(f"strip unreachable ({type(e).__name__}); "
                         f"holding (x{self._fails})")
            await asyncio.sleep(min(2.0, 0.2 * self._fails))

    @property
    def encoder(self):
        """The FrameEncoder for the connected controller's preset."""
        return self.services.encoder

    @property
    def last_rgb(self):
        """The colour currently on the strip, if the device layer knows it.

        Modes use this to start a fade from what is actually lit rather than
        from black.
        """
        return getattr(self.device, "last_rgb", None)

    def level(self):
        """The brightness factor 0..1: the user's level under the ceiling."""
        return (_ceiling(self.state.get("max_brightness", 100))
                * _ceiling(self.state.get("brightness", 100)))

    async def set(self, r, g, b):
        """Set the strip color, applying the brightness level and ceiling."""
        self._check_current()
        self.shown = (int(r), int(g), int(b))
        f = self.level()
        await self._guard(self.device.set_rgb(r * f, g * f, b * f))

    async def raw(self, frame):
        """Send a raw protocol frame (e.g. a built-in effect/speed command)."""
        self._check_current()
        await self._guard(self.device.send_frame(frame))

    async def sleep(self, dt):
        await asyncio.sleep(dt)
        self._check_current()


class Mode:
    name = "base"

    async def run(self, ctx):  # pragma: no cover - interface
        raise NotImplementedError

    def describe(self):
        return self.name
