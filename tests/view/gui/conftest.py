"""Desktop-app test fixtures: offscreen Qt, fakes, and a context per test."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from gui_fakes import FakeClient, FakeGuiServices, SyncBridge  # noqa: E402

from deskglow.view.gui import accent, theme  # noqa: E402
from deskglow.view.gui.context import AppContext  # noqa: E402
from deskglow.view.gui.poller import StatusPoller  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_globals():
    """Accent and palette are app-wide; start every test from the defaults."""
    accent.set_accent(theme.DEFAULT_ACCENT)
    theme.set_current(theme.DARK)
    yield
    accent.set_accent(theme.DEFAULT_ACCENT)
    theme.set_current(theme.DARK)


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def gui_services():
    return FakeGuiServices()


@pytest.fixture
def ctx(qapp, client, gui_services):
    """An AppContext over a synchronous bridge to the fake client."""
    from deskglow.view.gui import fonts
    fonts.load()
    bridge = SyncBridge(client)
    context = AppContext(bridge, StatusPoller(bridge), gui_services)
    yield context
    context.theme.stop()          # a test's context must not follow later tests' desktop

