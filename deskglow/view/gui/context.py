"""What every screen shares: the latest status, a way to send requests, the
local capabilities (start at login, shortcut, tray), and navigation."""
import logging

from PySide6.QtCore import QObject, Signal

from .accent import set_accent
from .themer import ThemeSwitch
from .vm.settings import Capability
from .vm.status import StatusView

log = logging.getLogger("deskglow.gui")


class AppContext(QObject):
    status_changed = Signal(object)     # StatusView
    local_changed = Signal()            # login / hotkey / tray capability
    navigate = Signal(str)              # page id: home effects sync focus settings setup
    error = Signal(str)                 # a request failed
    accent_changed = Signal(str)        # the strip's colour changed: repaint

    def __init__(self, bridge, poller, services=None, parent=None):
        super().__init__(parent)
        self.bridge, self.poller, self.services = bridge, poller, services
        self.status = StatusView()
        self.login = Capability(available=False, reason="Checking…")
        self.hotkey = Capability()
        self.tray_available = False
        self.last_error = ""
        poller.updated.connect(self._on_status)
        self.theme = ThemeSwitch(self, self)

    # ---- daemon ------------------------------------------------------------

    def send(self, req, callback=None, refresh=True):
        """Send one request; refresh status afterwards so the UI catches up."""
        def done(reply):
            if not reply.get("ok"):
                self.last_error = str(reply.get("error") or "request failed")
                log.warning("request %s failed: %s", req.get("cmd"), self.last_error)
                self.error.emit(self.last_error)
            if callback is not None:
                callback(reply)
            if refresh:
                self.poller.refresh()
        self.bridge.request(req, done)

    def _on_status(self, reply):
        self.status = StatusView(reply)
        changed = set_accent(self.status.accent)     # before anyone repaints
        self.status_changed.emit(self.status)
        if changed:
            self.accent_changed.emit(self.status.accent)

    # ---- local capabilities --------------------------------------------------

    def set_login(self, capability):
        self.login = capability
        self.local_changed.emit()

    def set_hotkey(self, capability):
        self.hotkey = capability
        self.local_changed.emit()

    def set_tray_available(self, available):
        self.tray_available = bool(available)
        self.local_changed.emit()

    def log_path(self):
        try:
            return self.services.storage.log_path()
        except Exception:
            return ""
