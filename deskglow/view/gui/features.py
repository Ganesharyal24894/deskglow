"""App-side features that live in the GUI process: start at login and the
global shortcut. Each degrades to a disabled toggle with a reason. (The theme
lives in themer.ThemeSwitch, on the context.)"""
from PySide6.QtCore import QObject, Qt, Signal

from .vm.settings import HOTKEY, Capability

NO_HOTKEY = "Not available on this desktop"
HOTKEY_REFUSED = "This desktop doesn't allow global shortcuts"


class Features(QObject):
    hotkey_pressed = Signal()        # emitted from whatever thread the hotkey uses

    def __init__(self, ctx, services, parent=None):
        super().__init__(parent)
        self.ctx, self.services = ctx, services
        self._hotkey, self._registered = None, False
        self.hotkey_pressed.connect(lambda: ctx.send({"cmd": "toggle"}),
                                    Qt.ConnectionType.QueuedConnection)
        ctx.status_changed.connect(self._follow)
        self._probe_hotkey()
        self.check_login()

    # ---- start at login ------------------------------------------------------

    def check_login(self):
        self.ctx.bridge.call(self.services.autostart.is_enabled, self._login_read)

    def _login_read(self, result):
        if isinstance(result, Exception):
            self.ctx.set_login(Capability(False, "Can't be changed on this system", False))
        else:
            self.ctx.set_login(Capability(True, "", bool(result)))

    def set_login(self, on):
        before = self.ctx.login.checked
        self.ctx.set_login(Capability(True, "", bool(on)))

        def done(result):
            if isinstance(result, Exception):
                self.ctx.set_login(Capability(True, "", before))
                self.ctx.error.emit(f"Couldn't change start at login: {result}")
        self.ctx.bridge.call(lambda: self.services.autostart.set_enabled(bool(on)), done)

    # ---- global shortcut -----------------------------------------------------

    def _probe_hotkey(self):
        try:
            self._hotkey = self.services.hotkey()
        except Exception:
            self._hotkey = None
            self.ctx.set_hotkey(Capability(False, NO_HOTKEY))

    def apply_hotkey(self, on):
        if self._hotkey is None or on == self._registered:
            return
        if not on:
            self._unregister()
            return
        try:
            ok = bool(self._hotkey.register(HOTKEY, self.hotkey_pressed.emit))
        except Exception:
            ok = False
        if ok:
            self._registered = True
        else:
            self.ctx.set_hotkey(Capability(False, HOTKEY_REFUSED))
            self.ctx.send({"cmd": "config", "key": "hotkey_on", "value": False})

    def _unregister(self):
        if self._registered and self._hotkey is not None:
            try:
                self._hotkey.unregister()
            except Exception:
                pass
        self._registered = False

    def _follow(self, status):
        if not status.reachable:
            return
        if self.ctx.hotkey.available:
            self.apply_hotkey(status.flag("hotkey_on"))

    def shutdown(self):
        self._unregister()
