"""Tray quick panel and tray icon (with and without a system tray)."""
import pytest
from gui_fakes import push
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QSystemTrayIcon

from deskglow.view.gui import tray as tray_mod
from deskglow.view.gui.screens.tray import TrayPanel


@pytest.fixture
def panel(qtbot, ctx, client):
    p = TrayPanel(ctx, popup=False)
    qtbot.addWidget(p)
    p.show()
    push(ctx, client)
    client.requests.clear()
    return p


def click(qtbot, w):
    qtbot.mouseClick(w, Qt.MouseButton.LeftButton)


def test_panel_shows_the_status(panel, ctx, client):
    assert panel.name.text() == "Desk strip"
    assert panel.status.text() == "Solid colour · connected"
    assert panel.power.isChecked() and panel.value.text() == "80%"
    push(ctx, client, mode="off", connected=False)
    assert panel.status.text() == "Off · standby" and not panel.power.isChecked()


def test_power_switch(qtbot, panel, ctx, client):
    click(qtbot, panel.power)
    assert client.sent() == [{"cmd": "off"}]


def test_swatch_sets_the_colour(qtbot, panel, client):
    click(qtbot, panel.swatches.buttons[1])
    assert client.sent() == [{"cmd": "set_mode", "mode": "solid",
                              "args": {"rgb": [255, 255, 255]}}]


@pytest.mark.parametrize("qid,mode", [("screen", "screen"), ("audio", "audio"),
                                      ("calm", "calm"), ("effects", "pattern")])
def test_quick_buttons(qtbot, panel, client, qid, mode):
    click(qtbot, panel.quick[qid])
    assert client.sent()[0]["mode"] == mode


def test_brightness(panel, client):
    panel.slider.setValue(40)
    assert client.sent() == [{"cmd": "config", "key": "brightness", "value": 40}]


def test_open_and_quit_signals(qtbot, panel):
    with qtbot.waitSignal(panel.open_app, timeout=500):
        click(qtbot, panel.open_button)
    with qtbot.waitSignal(panel.quit_app, timeout=500):
        click(qtbot, panel.quit_button)


def test_no_system_tray_degrades_gracefully(panel, ctx, monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    t = tray_mod.Tray(ctx, panel, lambda: None, lambda: None)
    assert t.icon is None and ctx.tray_available is False
    t.hide()                                   # harmless without an icon


@pytest.fixture
def tray(panel, ctx, monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    calls = []
    t = tray_mod.Tray(ctx, panel, lambda: calls.append("show"), lambda: calls.append("quit"))
    t.calls = calls
    yield t
    t.hide()


def test_tray_menu_actions(tray, ctx, client):
    assert ctx.tray_available is True
    actions = {a.text(): a for a in tray.menu.actions() if a.text()}
    assert list(actions) == ["Open Deskglow", "Turn off", "Quit"]
    actions["Open Deskglow"].trigger()
    actions["Turn off"].trigger()
    actions["Quit"].trigger()
    assert tray.calls == ["show", "quit"]
    assert client.sent() == [{"cmd": "off"}]


def test_menu_label_follows_power(tray, ctx, client):
    push(ctx, client, mode="off")
    assert tray.power_action.text() == "Turn on"


def test_clicking_the_icon_toggles_the_panel(tray, panel):
    panel.hide()
    tray._activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert panel.isVisible()
    tray._activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert not panel.isVisible()


def test_open_from_the_panel_hides_it_and_shows_the_window(tray, panel):
    panel.open_app.emit()
    assert not panel.isVisible() and tray.calls == ["show"]


def test_popup_is_placed_by_the_icon_and_kept_on_screen(panel):
    screen = QRect(0, 0, 1920, 1080)
    bottom_icon = QRect(1900, 1060, 20, 20)
    p = tray_mod.place_popup(panel, bottom_icon, screen)
    assert p.x() + panel.width() <= 1912 and p.y() + panel.height() <= 1060 - 8 + 1
    top_icon = QRect(100, 0, 20, 20)
    p = tray_mod.place_popup(panel, top_icon, screen)
    assert p.y() == top_icon.bottom() + 8 and p.x() == 8


def test_icon_pixmap_is_drawn_in_the_accent():
    pix = tray_mod.tray_icon_pixmap("#FF0000", 32)
    c = pix.toImage().pixelColor(16, 16)
    assert c.red() > 200 and c.green() < 50
