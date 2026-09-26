"""App-side features that live in the GUI process: start at login, the global
shortcut, and the theme. Each degrades to a disabled toggle with a reason."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import theme
from .style import stylesheet
from .vm.settings import HOTKEY, Capability

NO_HOTKEY = "Not available on this desktop"
HOTKEY_REFUSED = "This desktop doesn't allow global shortcuts"


def system_is_dark():
    try:
        return QGuiApplication.styleHints().colorScheme() != Qt.ColorScheme.Light
    except Exception:
        return True


def restyle(app=None):
    """Re-apply the palette (and accent) to every widget."""
    app = app or QApplication.instance()
    if app is None:
        return
    app.setStyleSheet(stylesheet(theme.current()))
    for w in app.allWidgets():
        refresh = getattr(w, "apply_theme", None)
        if refresh is not None:
            refresh()
        w.update()


class Features(QObject):
    hotkey_pressed = Signal()        # emitted from whatever thread the hotkey uses

    def __init__(self, ctx, services, parent=None):
        super().__init__(parent)
        self.ctx, self.services = ctx, services
        self._hotkey, self._registered = None, False
        self._theme_pref = None
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

    # ---- theme -----------------------------------------------------------------

    def apply_theme(self, preference):
        self._theme_pref = preference
        if theme.set_current(theme.resolve(preference, system_is_dark())):
            restyle()

    def _follow(self, status):
        if not status.reachable:
            return
        if self.ctx.hotkey.available:
            self.apply_hotkey(status.flag("hotkey_on"))
        pref = status.get("theme", "system")
        if pref != self._theme_pref:
            self.apply_theme(pref)

    def shutdown(self):
        self._unregister()
