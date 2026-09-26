"""Turn the strip on at local sunset (the "Turn on at sunset" setting).

The position comes from the LocationHint service (derived from the time zone,
no GPS). Without one there is nothing to schedule and `available()` is False,
so the app can explain why the setting is disabled. The clock and sleep are
injected so tests can run a whole day instantly.
"""
import asyncio
import datetime

from ..model.sun import sunset_utc

GRACE = datetime.timedelta(minutes=15)   # still "at sunset" this long after
MAX_WAIT = 300.0                         # re-check settings/clock this often (s)
NO_POSITION_WAIT = 3600.0


def local_now():
    return datetime.datetime.now().astimezone()


class SunsetWatcher:
    def __init__(self, location, is_enabled, is_off, turn_on,
                 clock=local_now, sleep=asyncio.sleep, log=None):
        self._location = location
        self._is_enabled = is_enabled
        self._is_off = is_off
        self._turn_on = turn_on
        self._clock = clock
        self._sleep = sleep
        self._log = log or (lambda _m: None)
        self._fired_on = None      # local date we last acted on

    def position(self):
        try:
            pos = self._location()
        except Exception:
            return None
        if pos is None:
            return None
        return (float(pos[0]), float(pos[1]))

    def available(self):
        return self.position() is not None

    def sunset_for(self, day):
        """Sunset on local date `day` as an aware datetime, or None."""
        pos = self.position()
        return None if pos is None else sunset_utc(pos[0], pos[1], day)

    async def tick(self, now):
        """Act if it is sunset now; return seconds until the next check."""
        pos = self.position()
        if pos is None:
            return NO_POSITION_WAIT
        today = now.date()
        sunset = self.sunset_for(today)
        if sunset is not None and self._fired_on != today and sunset <= now < sunset + GRACE:
            self._fired_on = today           # once a day, even if it was on already
            if self._is_enabled() and self._is_off():
                self._log("sunset: turning the strip on")
                await self._turn_on()
        return self._wait(now, today, sunset)

    def _wait(self, now, today, sunset):
        target = sunset
        if target is None or now >= target or self._fired_on == today:
            target = self.sunset_for(today + datetime.timedelta(days=1))
        if target is None:
            return MAX_WAIT
        return max(1.0, min(MAX_WAIT, (target - now).total_seconds()))

    async def run(self):
        while True:
            try:
                wait = await self.tick(self._clock())
            except Exception as e:   # never let the scheduler die
                self._log(f"sunset: {type(e).__name__}: {e}")
                wait = MAX_WAIT
            await self._sleep(wait)
