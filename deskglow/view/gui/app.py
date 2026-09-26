"""Assemble the desktop app: bridge, poller, pages, window, tray."""
import sys

from PySide6.QtWidgets import QApplication

from ...controller.client import DaemonClient
from ...controller.settings import SettingsStore
from . import fonts, theme
from .bridge import ThreadBridge
from .context import AppContext
from .features import Features
from .poller import StatusPoller
from .screens.effects import EffectsPage
from .screens.focus import FocusPage
from .screens.home import HomePage
from .screens.settings import SettingsPage
from .screens.setup import SetupPage
from .screens.sync import SyncPage
from .screens.tray import TrayPanel
from .style import stylesheet
from .themer import restyle
from .tray import Tray
from .window import MainWindow


class UI:
    """Everything the app owns. `client` is a DaemonClient (or a fake)."""

    def __init__(self, app, client, services, tray=True, bridge=None):
        self.app = app
        fonts.load()
        app.setFont(fonts.sans(14))
        app.setStyleSheet(stylesheet(theme.current()))
        self.bridge = bridge if bridge is not None else ThreadBridge(client)
        self.poller = StatusPoller(self.bridge)
        self.ctx = ctx = AppContext(self.bridge, self.poller, services)
        self.features = Features(ctx, services)
        self.pages = {
            "home": HomePage(ctx),
            "effects": EffectsPage(ctx, getattr(services, "preset", None)),
            "sync": SyncPage(ctx),
            "focus": FocusPage(ctx),
            "settings": SettingsPage(ctx, self.features),
        }
        self.setup = SetupPage(ctx)
        self.window = MainWindow(ctx, self.pages, self.setup)
        self.panel = TrayPanel(ctx, popup=tray)
        self.tray = Tray(ctx, self.panel, self.show_window, self.quit) if tray else None
        if not tray:
            ctx.set_tray_available(False)
        app.setQuitOnLastWindowClosed(not ctx.tray_available)
        ctx.accent_changed.connect(lambda _c: restyle(self.app))
        self.poller.start()

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def quit(self):
        self.window.quitting = True
        self.shutdown()
        self.app.quit()

    def shutdown(self):
        self.poller.stop()
        self.ctx.theme.stop()
        self.features.shutdown()
        if self.tray is not None:
            self.tray.hide()
        self.bridge.stop()


def build_ui(app, client, services, tray=True, bridge=None):
    return UI(app, client, services, tray, bridge)


def run(services, argv=None):
    """The `deskglow-gui` entry point, after the app layer built `services`."""
    app = QApplication.instance() or QApplication(list(argv if argv is not None else sys.argv))
    app.setApplicationName("Deskglow")
    app.setDesktopFileName("deskglow")
    client = DaemonClient(services.ipc_client, services.autostart, services.process)
    ui = UI(app, client, services)
    if not SettingsStore(services.storage).get_address():
        ui.window.go("setup")
    ui.window.show()
    code = app.exec()
    ui.shutdown()
    return code
