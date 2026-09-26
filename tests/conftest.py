"""Shared test fixtures.

Every test in this suite runs offline and headless: no Bluetooth adapter, no X
server, no PipeWire, no network, and no writes outside a tmp dir. Shared fakes
for the service interfaces live in tests/fakes.py.
"""
import asyncio
import os
import sys

import pytest

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TESTS))   # the repo root: `import deskglow`
sys.path.insert(0, TESTS)                    # `from fakes import ...`

from fakes import FakeDevice, make_services  # noqa: E402


# ---------------------------------------------------------------- isolation --

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Point HOME and the runtime dir at tmp so no test can touch the real
    ~/.config/deskglow, ~/.config/sc295 or a live daemon socket."""
    home = tmp_path / "home"
    run_dir = tmp_path / "run"
    home.mkdir()
    run_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(run_dir))
    monkeypatch.delenv("DESKGLOW_ADDRESS", raising=False)
    monkeypatch.delenv("SC295_ADDRESS", raising=False)
    return home


# ------------------------------------------------------------------- fakes ---

@pytest.fixture
def fake_device():
    return FakeDevice()


@pytest.fixture
def services():
    """A Services bundle made of fakes (see tests/fakes.py)."""
    return make_services()


@pytest.fixture
def make_ctx():
    """Build a ModeContext wired to a FakeDevice and fake services."""
    from deskglow.controller.modes.base import ModeContext

    def _make(device=None, state=None, is_current=None, services=None):
        device = device or FakeDevice()
        state = state if state is not None else {"max_brightness": 100}
        logs = []
        ctx = ModeContext(device, state, logs.append, is_current=is_current,
                          services=services or make_services())
        ctx.logs = logs
        return ctx

    return _make


async def run_briefly(coro_func, ctx, *, until, timeout=5.0):
    """Run a mode until `until(ctx)` is true, then cancel it.

    Modes loop forever by design; this drives one far enough to assert on its
    output without hanging the suite.
    """
    task = asyncio.ensure_future(coro_func(ctx))
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while not until(ctx):
            if task.done():
                await task            # surface the mode's own exception
                break
            if asyncio.get_event_loop().time() > deadline:
                raise AssertionError("mode did not produce expected output in time")
            await asyncio.sleep(0.005)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    return task


@pytest.fixture
def run_mode():
    return run_briefly
