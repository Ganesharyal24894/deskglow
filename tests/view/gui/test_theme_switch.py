"""Dark/light switching: sidebar switch, tray button, Settings, System mode."""
import pytest
from gui_fakes import HeldBridge, SyncBridge, push
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel

from deskglow.view.gui import icons, theme
from deskglow.view.gui.screens.settings import SettingsPage
from deskglow.view.gui.screens.setup import SetupPage
from deskglow.view.gui.screens.tray import TrayPanel
from deskglow.view.gui.window import MainWindow


def theme_requests(client):
    return [r["value"] for r in client.sent("config") if r["key"] == "theme"]


@pytest.fixture
def win(qtbot, ctx, client):
    desktop_scheme(Qt.ColorScheme.Dark)
    pages = {p: QLabel(p) for p in ("home", "effects", "sync", "focus")}
    pages["settings"] = SettingsPage(ctx)
    w = MainWindow(ctx, pages, SetupPage(ctx))
    qtbot.addWidget(w)
    w.show()
    push(ctx, client, theme="dark")
    client.requests.clear()
    return w


def desktop_scheme(scheme):
    """Fake the desktop switching its colour scheme."""
    QGuiApplication.styleHints().colorSchemeChanged.emit(scheme)


def click(qtbot, widget):
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def test_sidebar_switch_flips_saves_and_rethemes(qtbot, win, client):
    row = win.shell.sidebar.dark_mode
    assert row.switch.isChecked() and row.icon.markup == icons.MOON
    click(qtbot, row.switch)
    assert theme_requests(client) == ["light"]
    assert theme.current() is theme.LIGHT
    assert not row.switch.isChecked() and row.icon.markup == icons.SUN
    assert theme.LIGHT.bg in QApplication.instance().styleSheet()
    card = win.shell.sidebar.card
    assert theme.LIGHT.text.lower() in card.name.styleSheet().lower(), "labels re-read colours"
    click(qtbot, row.switch)
    assert theme_requests(client) == ["light", "dark"] and theme.current() is theme.DARK


def test_the_switch_shows_the_effective_theme_in_system_mode(win, ctx, client):
    push(ctx, client, theme="system")          # the desktop is dark (fixture)
    row = win.shell.sidebar.dark_mode
    assert theme.current() is theme.DARK and row.switch.isChecked()


def test_system_follows_the_desktop_colour_scheme_live(win, ctx, client):
    push(ctx, client, theme="system")
    desktop_scheme(Qt.ColorScheme.Light)
    assert theme.current() is theme.LIGHT
    assert not win.shell.sidebar.dark_mode.switch.isChecked()
    desktop_scheme(Qt.ColorScheme.Dark)
    assert theme.current() is theme.DARK
    assert theme_requests(client) == [], "following the desktop saves nothing"


def test_an_explicit_choice_ignores_the_desktop(win, ctx, client):
    push(ctx, client, theme="dark")
    desktop_scheme(Qt.ColorScheme.Light)
    assert theme.current() is theme.DARK
    desktop_scheme(Qt.ColorScheme.Dark)


def test_settings_follows_the_switch_and_offers_system(qtbot, win, ctx, client):
    settings = win.shell.pages["settings"]
    assert settings.themes.current == "dark"
    ctx.bridge = HeldBridge(client)            # before the daemon answers:
    click(qtbot, win.shell.sidebar.dark_mode.switch)
    assert settings.themes.current == "light"
    ctx.bridge.release()
    ctx.bridge = SyncBridge(client)
    seg = settings.themes
    qtbot.mouseClick(seg, Qt.MouseButton.LeftButton, pos=seg.rects()["system"].center().toPoint())
    assert theme_requests(client) == ["light", "system"]
    assert theme.current() is theme.DARK and seg.current == "system"
    assert win.shell.sidebar.dark_mode.switch.isChecked()


def test_a_poll_from_before_the_choice_does_not_revert_it(qtbot, win, ctx, client):
    client.replies["config"] = {"ok": True}    # the daemon hasn't stored it yet
    click(qtbot, win.shell.sidebar.dark_mode.switch)
    push(ctx, client, theme="dark")
    assert theme.current() is theme.LIGHT
    client.status["theme"] = "light"
    push(ctx, client)
    push(ctx, client, theme="dark")            # changed elsewhere later: follow it
    assert theme.current() is theme.DARK


def test_a_refused_choice_is_undone_by_the_next_status(qtbot, win, ctx, client):
    client.replies["config"] = {"ok": False, "error": "nope"}
    click(qtbot, win.shell.sidebar.dark_mode.switch)
    push(ctx, client)
    assert theme.current() is theme.DARK


def test_tray_button_flips_the_theme(qtbot, ctx, client):
    panel = TrayPanel(ctx, popup=False)
    qtbot.addWidget(panel)
    panel.show()
    push(ctx, client, theme="dark")
    button = panel.theme_button
    assert (button.width(), button.height()) == (36, 36)
    assert button.icon_markup == icons.SUN and button.accessibleName() == "Switch to light mode"
    strip_before = panel.strip.height()
    click(qtbot, button)
    assert theme_requests(client) == ["light"] and theme.current() is theme.LIGHT
    assert button.icon_markup == icons.MOON and button.accessibleName() == "Switch to dark mode"
    assert panel.strip.height() == strip_before + 24, "the strip sits on a dark stage"
    click(qtbot, button)
    assert theme_requests(client) == ["light", "dark"] and theme.current() is theme.DARK


@pytest.mark.parametrize("palette, track, knob", [
    (theme.LIGHT, "#8C633D", "#FFFFFF"), (theme.DARK, "#FFB46E", "#141413")])
def test_switch_on_is_an_ink_track_with_the_palette_knob(qtbot, palette, track, knob):
    from deskglow.view.gui.widgets.controls import Toggle
    theme.set_current(palette)
    t = Toggle()
    qtbot.addWidget(t)
    t.setChecked(True)
    img = t.grab().toImage()
    assert img.pixelColor(8, 14).name().upper() == track
    assert img.pixelColor(34, 14).name().upper() == knob
