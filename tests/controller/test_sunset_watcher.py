"""SunsetWatcher: turns the strip on at local sunset, with an injected clock."""
import asyncio
import datetime as dt

import pytest

from deskglow.controller import sunset as sunset_mod
from deskglow.controller.sunset import SunsetWatcher
from deskglow.model.sun import sunset_utc

LONDON = (51.5074, -0.1278)
BST = dt.timezone(dt.timedelta(hours=1))
DAY = dt.date(2024, 6, 21)
SUNSET = sunset_utc(*LONDON, DAY)          # ~20:21 UTC


class Rig:
    def __init__(self, enabled=True, off=True, position=LONDON):
        self.enabled, self.off, self.position = enabled, off, position
        self.turned_on = 0
        self.w = SunsetWatcher(lambda: self.position, lambda: self.enabled,
                               lambda: self.off, self.turn_on)

    async def turn_on(self):
        self.turned_on += 1


def at(delta_minutes):
    return (SUNSET + dt.timedelta(minutes=delta_minutes)).astimezone(BST)


async def test_turns_on_at_sunset_when_enabled_and_off():
    r = Rig()
    await r.w.tick(at(-1))
    assert r.turned_on == 0
    await r.w.tick(at(0.5))
    assert r.turned_on == 1


async def test_fires_only_once_per_day():
    r = Rig()
    await r.w.tick(at(1))
    await r.w.tick(at(3))
    assert r.turned_on == 1


@pytest.mark.parametrize("enabled,off", [(False, True), (True, False)])
async def test_does_nothing_when_disabled_or_already_on(enabled, off):
    r = Rig(enabled=enabled, off=off)
    await r.w.tick(at(1))
    assert r.turned_on == 0


async def test_long_after_sunset_it_waits_for_tomorrow():
    """Starting the daemon at 23:00 must not suddenly light the strip."""
    r = Rig()
    wait = await r.w.tick(at(120))
    assert r.turned_on == 0
    assert wait == sunset_mod.MAX_WAIT


async def test_waits_until_sunset_when_it_is_close():
    r = Rig()
    assert await r.w.tick(at(-2)) == pytest.approx(120.0, abs=0.01)


async def test_no_position_means_unavailable_and_no_schedule():
    r = Rig(position=None)
    assert r.w.available() is False
    assert await r.w.tick(at(1)) == sunset_mod.NO_POSITION_WAIT
    assert r.turned_on == 0


async def test_a_broken_location_service_counts_as_unavailable():
    def boom():
        raise RuntimeError("tz database missing")
    w = SunsetWatcher(boom, lambda: True, lambda: True, None)
    assert w.available() is False


async def test_polar_summer_never_fires():
    r = Rig(position=(78.2, 15.6))     # Svalbard, midnight sun
    for minutes in range(0, 1440, 60):
        await r.w.tick(dt.datetime(2024, 6, 21, tzinfo=dt.timezone.utc)
                       + dt.timedelta(minutes=minutes))
    assert r.turned_on == 0


async def test_run_loop_uses_the_injected_clock_and_sleep():
    times = iter([at(-0.5), at(0.5)])
    sleeps = []
    r = Rig()

    async def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            raise StopAsyncIteration

    w = SunsetWatcher(lambda: LONDON, lambda: True, lambda: True, r.turn_on,
                      clock=lambda: next(times), sleep=fake_sleep)
    with pytest.raises(StopAsyncIteration):
        await w.run()
    assert r.turned_on == 1
    assert sleeps[0] == pytest.approx(30.0, abs=0.01)


async def test_daemon_wires_the_watcher_to_its_state(monkeypatch):
    from daemon_support import make_daemon, quiesce
    d = make_daemon()
    d.sunset._location = lambda: LONDON
    d.state["sunset_on"] = True
    await d.sunset.tick(at(1))
    assert d.mode_name == "solid" and d.mode_args == {"rgb": [255, 180, 110]}
    await quiesce(d)


async def test_the_daemon_runs_the_watcher_in_the_background():
    from daemon_support import make_daemon
    d = make_daemon()
    ran = []

    async def fake_run():
        ran.append(True)
    d.sunset.run = fake_run
    d.start_background_tasks()
    await asyncio.sleep(0.01)
    assert ran == [True]
    await d.shutdown_background_tasks()
