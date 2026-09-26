"""Settings: strip card, App toggles (incl. disabled states), theme, about."""
import pytest
from fakes import FakeAutostart
from gui_fakes import FakeGuiServices, FakeHotkey, push
from PySide6.QtCore import Qt

from deskglow.view.gui import theme
from deskglow.view.gui.features import Features
from deskglow.view.gui.screens import settings as settings_screen
from deskglow.view.gui.screens.settings import SettingsPage


def make(qtbot, ctx, client, services, **status_over):
    ctx.services = services
    features = Features(ctx, services)
    ctx.set_tray_available(True)
    page = SettingsPage(ctx, features)
    qtbot.addWidget(page)
    page.resize(824, 720)
    page.show()
    push(ctx, client, **status_over)
    client.requests.clear()
    return page, features


@pytest.fixture
def page(qtbot, ctx, client):
    return make(qtbot, ctx, client, FakeGuiServices(hotkey=FakeHotkey()))[0]


def click(qtbot, w):
    qtbot.mouseClick(w, Qt.MouseButton.LeftButton)


def test_strip_card_shows_the_status(page):
    st = page.strip
    assert st["name"].text() == "Desk strip"
    assert st["address"].text() == "A4:C1:38:5E:22:9B" and st["model"].text() == "MELK-OA10"
    assert st["ceiling"].value() == 100 and st["ceil_value"].text() == "100%"


def test_renaming_the_strip(page, client):
    page.strip["name"].setText("Shelf")
    page.strip["name"].editingFinished.emit()
    assert client.sent() == [{"cmd": "config", "key": "strip_name", "value": "Shelf"}]


def test_ceiling_slider(page, client):
    page.strip["ceiling"].setValue(85)
    assert client.sent() == [{"cmd": "config", "key": "max_brightness", "value": 85}]


def test_find_another_strip_opens_setup(qtbot, page, ctx):
    went = []
    ctx.navigate.connect(went.append)
    click(qtbot, page.strip["find"])
    assert went == ["setup"]


def test_forget_needs_a_second_click(qtbot, page, ctx, client):
    went = []
    ctx.navigate.connect(went.append)
    click(qtbot, page.strip["forget"])
    assert page.strip["forget"].text() == "Confirm forget" and client.sent() == []
    click(qtbot, page.strip["forget"])
    assert client.sent() == [{"cmd": "forget"}] and went == ["setup"]


def test_forget_confirmation_times_out(qtbot, page, client, monkeypatch):
    monkeypatch.setattr(settings_screen, "CONFIRM_MS", 30)
    click(qtbot, page.strip["forget"])
    qtbot.waitUntil(lambda: page.strip["forget"].text() == "Forget", timeout=2000)
    click(qtbot, page.strip["forget"])
    assert client.sent() == []


@pytest.mark.parametrize("tid,key", [("tray", "tray_on"), ("hotkey", "hotkey_on"),
                                     ("sunset", "sunset_on")])
def test_daemon_backed_toggles(qtbot, page, client, tid, key):
    switch = page.toggles[tid].switch
    before = switch.isChecked()
    click(qtbot, switch)
    assert {"cmd": "config", "key": key, "value": not before} in client.sent()


def test_start_at_login_uses_the_autostart_service(qtbot, ctx, client):
    auto = FakeAutostart(enabled=False)
    page, _f = make(qtbot, ctx, client, FakeGuiServices(FakeHotkey(), auto))
    switch = page.toggles["login"].switch
    assert switch.isEnabled() and not switch.isChecked()
    click(qtbot, switch)
    assert auto.set_calls == [True] and auto.enabled and switch.isChecked()
    assert client.sent() == []


def test_start_at_login_failure_reverts_and_reports(qtbot, ctx, client):
    auto = FakeAutostart(enabled=False, error=OSError("systemctl refused"))
    page, _f = make(qtbot, ctx, client, FakeGuiServices(FakeHotkey(), auto))
    errors = []
    ctx.error.connect(errors.append)
    click(qtbot, page.toggles["login"].switch)
    assert not page.toggles["login"].switch.isChecked()
    assert "systemctl refused" in errors[0]


def test_unreadable_autostart_disables_the_toggle(qtbot, ctx, client):
    class Broken(FakeAutostart):
        def is_enabled(self):
            raise OSError("no service manager")
    page, _f = make(qtbot, ctx, client, FakeGuiServices(FakeHotkey(), Broken()))
    row = page.toggles["login"]
    assert not row.switch.isEnabled() and row.desc.text() == "Can't be changed on this system"


def test_shortcut_unavailable_when_the_factory_raises(qtbot, ctx, client):
    page, _f = make(qtbot, ctx, client, FakeGuiServices(hotkey=None))
    row = page.toggles["hotkey"]
    assert not row.switch.isEnabled() and row.desc.text() == "Not available on this desktop"


def test_shortcut_refused_by_the_desktop_turns_off_and_explains(qtbot, ctx, client):
    hk = FakeHotkey(ok=False)
    page, _f = make(qtbot, ctx, client, FakeGuiServices(hotkey=hk))
    click(qtbot, page.toggles["hotkey"].switch)
    row = page.toggles["hotkey"]
    assert hk.registered and not row.switch.isEnabled()
    assert row.desc.text() == "This desktop doesn't allow global shortcuts"
    assert client.sent()[-1] == {"cmd": "config", "key": "hotkey_on", "value": False}


def test_sunset_needs_a_time_zone(qtbot, ctx, client):
    page, _f = make(qtbot, ctx, client, FakeGuiServices(FakeHotkey()), sunset_available=False)
    row = page.toggles["sunset"]
    assert not row.switch.isEnabled() and row.desc.text() == "Needs your time zone to be set"


def test_no_tray_disables_keep_running(qtbot, page, ctx):
    ctx.set_tray_available(False)
    assert not page.toggles["tray"].switch.isEnabled()


def test_theme_choice_is_saved_and_light_stays_dark_for_now(qtbot, page, client):
    seg = page.themes
    qtbot.mouseClick(seg, Qt.MouseButton.LeftButton, pos=seg.rects()["light"].center().toPoint())
    assert client.sent() == [{"cmd": "config", "key": "theme", "value": "light"}]
    assert theme.current() is theme.DARK


def test_about_buttons_open_logs_and_github(qtbot, page, monkeypatch):
    opened = []
    monkeypatch.setattr(page, "open_url", lambda url: opened.append(url.toString()))
    click(qtbot, page.about["logs"])
    click(qtbot, page.about["github"])
    assert opened[0].endswith("/fake/config/deskglow/daemon.log")
    assert opened[1].startswith("https://github.com/")


def test_a_registered_light_palette_is_applied_when_picked(qtbot, page, monkeypatch):
    light = theme.Palette(**{**theme.DARK.__dict__, "name": "light", "bg": "#FAFAFA"})
    monkeypatch.setitem(theme.PALETTES, "light", light)
    seg = page.themes
    qtbot.mouseClick(seg, Qt.MouseButton.LeftButton, pos=seg.rects()["light"].center().toPoint())
    assert theme.current() is light
    assert "#FAFAFA" in qtbot_app_stylesheet()


def qtbot_app_stylesheet():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance().styleSheet()
