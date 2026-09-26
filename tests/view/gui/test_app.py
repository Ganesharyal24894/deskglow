"""The assembled app: build, global shortcut, accent/theme restyle, entry point."""
import threading

import pytest
from gui_fakes import FakeClient, FakeGuiServices, FakeHotkey, SyncBridge, push

from deskglow.app import gui as app_gui
from deskglow.view.gui import accent
from deskglow.view.gui import app as gui_app
from deskglow.view.gui.app import build_ui


@pytest.fixture
def ui(qtbot, qapp):
    client = FakeClient(hotkey_on=True)
    hk = FakeHotkey()
    u = build_ui(qapp, client, FakeGuiServices(hotkey=hk), tray=False, bridge=SyncBridge(client))
    qtbot.addWidget(u.window)
    u.client, u.hk = client, hk
    yield u
    u.shutdown()


def test_builds_every_screen_and_polls_status(ui):
    assert set(ui.pages) == {"home", "effects", "sync", "focus", "settings"}
    assert {"cmd": "status"} in ui.client.requests
    assert ui.ctx.status.reachable and ui.window.current_page() == "home"
    assert ui.ctx.tray_available is False


def test_shortcut_registered_when_on_and_toggles_power(qtbot, ui):
    assert ui.hk.registered and ui.hk.registered[0][0] == "<ctrl>+<alt>+l"
    callback = ui.hk.registered[0][1]
    ui.client.requests.clear()
    t = threading.Thread(target=callback)     # the hotkey fires on its own thread
    t.start()
    t.join()
    qtbot.waitUntil(lambda: ui.client.sent() == [{"cmd": "toggle"}], timeout=2000)


def test_turning_the_shortcut_off_unregisters_it(ui):
    push(ui.ctx, ui.client, hotkey_on=False)
    assert ui.hk.unregistered == 1
    ui.shutdown()
    assert ui.hk.unregistered == 1        # nothing left to release


def test_a_new_strip_colour_restyles_the_app(ui, monkeypatch):
    restyled = []
    monkeypatch.setattr(gui_app, "restyle", lambda app=None: restyled.append(app))
    ui.ctx.accent_changed.connect(lambda c: restyled.append(c))
    push(ui.ctx, ui.client, color="#3DDC97", args={"rgb": [61, 220, 151]})
    assert accent.accent() == "#3DDC97" and "#3DDC97" in restyled
    assert ui.app in restyled, "the app is restyled with the new accent"
    brand = ui.window.shell.sidebar.brand.bar
    brand.apply_theme()
    assert brand.graphicsEffect().color().name().upper() == "#3DDC97"


def test_quit_stops_everything(ui, monkeypatch):
    quits = []
    monkeypatch.setattr(ui.app, "quit", lambda: quits.append(1))
    ui.quit()
    assert quits == [1] and ui.window.quitting


def test_entry_point_reports_a_missing_platform(monkeypatch, capsys):
    def boom():
        raise RuntimeError("Deskglow has no drivers for 'plan9' yet")
    monkeypatch.setattr(app_gui, "build_services", boom)
    assert app_gui.main([]) == 1
    assert "plan9" in capsys.readouterr().err


def test_entry_point_runs_the_app_with_built_services(monkeypatch):
    seen = {}
    monkeypatch.setattr(app_gui, "build_services", lambda: "services")
    monkeypatch.setattr(gui_app, "run", lambda services, argv: seen.update(s=services) or 0)
    assert app_gui.main(["x"]) == 0 and seen == {"s": "services"}


def test_run_opens_setup_when_no_strip_is_saved(qapp, monkeypatch):
    from fakes import FakeIpcClient, make_services
    from PySide6.QtWidgets import QApplication
    built = {}
    real_ui = gui_app.UI

    def spy(*a, **kw):
        built["ui"] = real_ui(*a, **kw)
        return built["ui"]

    monkeypatch.setattr(gui_app, "UI", spy)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    services = make_services(ipc_client=FakeIpcClient({"ok": True, "configured": False}))
    assert gui_app.run(services, []) == 0
    assert built["ui"].window.current_page() == "setup"
    built["ui"].window.close()
