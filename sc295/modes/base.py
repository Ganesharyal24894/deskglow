"""Mode base class and the context modes use to drive the strip."""
import asyncio


class ModeContext:
    """Everything a mode needs: a way to set color, plus shared state.

    set() never raises: a BLE outage is swallowed and self-throttled, so a mode
    keeps running (and resumes the moment the strip is reachable again) instead
    of dying or busy-looping.
    """

    def __init__(self, device, state, logger):
        self.device = device
        self.state = state
        self.log = logger
        self._fails = 0

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

    async def set(self, r, g, b):
        """Set the strip color, applying the global brightness ceiling."""
        f = self.state.get("max_brightness", 100) / 100.0
        await self._guard(self.device.set_rgb(r * f, g * f, b * f))

    async def raw(self, frame):
        """Send a raw protocol frame (e.g. a built-in effect/speed command)."""
        await self._guard(self.device.send_frame(frame))

    async def sleep(self, dt):
        await asyncio.sleep(dt)


class Mode:
    name = "base"

    async def run(self, ctx):  # pragma: no cover - interface
        raise NotImplementedError

    def describe(self):
        return self.name
