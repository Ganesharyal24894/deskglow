"""Main window: navigation, first-run Setup, close-to-tray."""
import pytest
from gui_fakes import push
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel

from deskglow.view.gui.screens.setup import SetupPage
from deskglow.view.gui.window import MainWindow


@pytest.fixture
def win(qtbot, ctx, client):
    pages = {p: QLabel(p) for p in ("home", "effects", "sync", "focus", "settings")}
    w = MainWindow(ctx, pages, SetupPage(ctx))
    qtbot.addWidget(w)
    w.show()
    push(ctx, client)
    client.requests.clear()
    return w


def test_default_size_matches_the_design(win):
    assert (win.width(), win.height()) == (1040, 720)
    assert win.shell.sidebar.width() == 216


@pytest.mark.parametrize("page", ["effects", "sync", "focus", "settings", "home"])
def test_sidebar_navigation(qtbot, win, page):
    qtbot.mouseClick(win.shell.sidebar.items[page], Qt.MouseButton.LeftButton)
    assert win.current_page() == page
    assert [p for p, i in win.shell.sidebar.items.items() if i.active] == [page]


def test_device_card_shows_connection_and_signal(win, ctx, client):
    card = win.shell.sidebar.card
    assert (card.name.text(), card.state.text(), card.rssi.text()) == (
        "Desk strip", "Connected", "-58 dBm")
    push(ctx, client, connected=False, mode="calm", name="Shelf")
    assert (card.name.text(), card.state.text(), card.dot.colour) == (
        "Shelf", "Connecting…", "warn")


def test_no_strip_configured_opens_setup(qtbot, ctx, client):
    pages = {p: QLabel(p) for p in ("home", "effects", "sync", "focus", "settings")}
    w = MainWindow(ctx, pages, SetupPage(ctx))
    qtbot.addWidget(w)
    push(ctx, client, configured=False)
    assert w.current_page() == "setup"


def test_forgetting_the_strip_opens_setup(win, ctx, client):
    push(ctx, client, configured=False)
    assert win.current_page() == "setup"


def test_a_stale_unconfigured_reply_does_not_bounce_back_to_setup(win, ctx, client):
    push(ctx, client, configured=False)
    win.go("home")                        # setup finished
    push(ctx, client, configured=False)   # a reply that raced the save
    assert win.current_page() == "home"


def test_daemon_down_is_not_mistaken_for_no_strip(win, ctx, client):
    client.status = {"ok": False, "error": "down"}
    ctx.poller.poll()
    assert win.current_page() == "home"


def close(win):
    ev = QCloseEvent()
    win.closeEvent(ev)
    return ev.isAccepted()


def test_close_hides_to_the_tray_when_that_is_on(win, ctx, client):
    ctx.set_tray_available(True)
    push(ctx, client, tray_on=True)
    assert close(win) is False and not win.isVisible()


def test_close_quits_when_the_tray_setting_is_off(win, ctx, client):
    ctx.set_tray_available(True)
    push(ctx, client, tray_on=False)
    assert close(win) is True


def test_close_quits_without_a_system_tray(win, ctx, client):
    ctx.set_tray_available(False)
    push(ctx, client, tray_on=True)
    assert close(win) is True


def test_quit_always_closes(win, ctx, client):
    ctx.set_tray_available(True)
    win.quitting = True
    assert close(win) is True
