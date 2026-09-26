"""Connect backoff: ramping cooldown, short-circuiting, and resetting it."""
import pytest

from deskglow.controller import connect
from device_harness import expect_failed_connect, make_device


async def test_consecutive_failures_ramp_the_cooldown_and_cap_at_300s(
        ble, monkeypatch, clock):
    """5s, 10s, 15s ... so a strip that is simply switched off is not retried
    hundreds of times overnight — but never longer than 5 minutes."""
    monkeypatch.setattr(connect, "SCAN_TIMEOUT", 0.0)
    ble.fail_connects()
    ble.discoverable = []
    dev = make_device(ble)

    for n in range(1, 62):
        await expect_failed_connect(dev)
        assert dev.consecutive_failures == n
        expected = min(300.0, 5.0 * n)
        clock.advance(expected - 0.01)
        assert dev.in_cooldown(), f"cooldown after {n} failures was shorter than {expected}s"
        clock.advance(0.02)
        assert not dev.in_cooldown(), f"cooldown after {n} failures exceeded {expected}s"


async def test_failure_logging_is_throttled(ble, logs, clock):
    """Failures 1, 2 and every 5th are logged, so an overnight outage stays quiet."""
    ble.fail_connects()
    dev = make_device(ble, logs)
    for _ in range(10):
        await expect_failed_connect(dev)
        clock.advance(400.0)             # past any cooldown
    lines = [m for m in logs if "backing off" in m]
    assert [m.split("(x")[1].split(")")[0] for m in lines] == ["1", "2", "5", "10"]


async def test_cooldown_short_circuits_without_touching_the_radio(ble):
    """While backing off we must not construct a client or start a scan at all."""
    ble.fail_connects()
    ble.discoverable = []
    dev = make_device(ble)
    await expect_failed_connect(dev)

    mark = ble.mark()
    with pytest.raises(ConnectionError, match="cooldown"):
        await dev.ensure_connected()
    assert ble.clients_since(mark) == [], "attempted a connect while in cooldown"
    assert ble.scans == mark[2], "started a scan while in cooldown"


async def test_reset_backoff_clears_both_the_cooldown_and_the_counter(ble, clock):
    """Re-running `deskglow setup` must make the next attempt happen immediately."""
    ble.fail_connects()
    ble.discoverable = []
    dev = make_device(ble)
    await expect_failed_connect(dev)
    assert dev.in_cooldown() and dev.consecutive_failures == 1

    dev.reset_backoff()
    assert not dev.in_cooldown()
    assert dev.consecutive_failures == 0

    mark = ble.mark()
    ble.default_connect_error = None
    await dev.ensure_connected()
    assert ble.clients_since(mark), "reset_backoff did not allow an immediate retry"


async def test_successful_connect_clears_the_failure_counter(ble):
    """One good connect wipes the failure history the watchdog watches."""
    ble.fail_connects()
    dev = make_device(ble)
    await expect_failed_connect(dev)
    dev.reset_backoff()
    ble.default_connect_error = None
    await dev.ensure_connected()
    assert dev.consecutive_failures == 0
