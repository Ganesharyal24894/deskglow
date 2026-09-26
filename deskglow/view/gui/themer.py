"""Dark / light switching: the Theme preference (system | dark | light), the
palette it resolves to, and re-theming every open window when either the
preference or the desktop's colour scheme changes.

The preference is persisted by the daemon (config key "theme"); the sidebar
switch and the tray button flip between dark and light, Settings can also
pick System, which follows QStyleHints.colorScheme() live."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import theme
from .style import stylesheet
from .vm.settings import theme_request


def system_is_dark():
    """The desktop's colour scheme (dark when unknown)."""
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


class ThemeSwitch(QObject):
    """Owns the Theme preference. `changed` fires after a re-theme or a
    preference change, so controls showing either can follow."""

    changed = Signal()

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.pref = None                   # unknown until the first status
        self._sent = None                  # a choice the daemon hasn't echoed yet
        self._system_dark = system_is_dark()
        self._hints = QGuiApplication.styleHints()
        if self._hints is not None:
            self._hints.colorSchemeChanged.connect(self._scheme_changed)
        ctx.status_changed.connect(self._follow)

    def stop(self):
        """Stop following the desktop (app shutdown)."""
        if self._hints is not None:
            self._hints.colorSchemeChanged.disconnect(self._scheme_changed)
            self._hints = None

    def is_dark(self):
        """True when the palette on screen is the dark one."""
        return theme.current().name == "dark"

    def apply(self, pref):
        """Show `pref` without saving it."""
        self.pref = pref
        if theme.set_current(theme.resolve(pref, self._system_dark)):
            restyle()
        self.changed.emit()

    def choose(self, pref):
        """The user picked `pref`: show it now and save it in the daemon."""
        self._sent = pref
        self.apply(pref)
        self.ctx.send(theme_request(pref), self._saved)

    def flip(self):
        """The sidebar switch / tray button: dark <-> light."""
        self.choose("light" if self.is_dark() else "dark")

    def _saved(self, reply):
        if not reply.get("ok"):
            self._sent = None              # the next status puts the saved one back

    def _scheme_changed(self, scheme):
        self._system_dark = scheme != Qt.ColorScheme.Light
        if self.pref == "system":
            self.apply("system")

    def _follow(self, status):
        if not status.reachable:
            return
        pref = status.get("theme", "system")
        if self._sent is not None:
            if pref != self._sent:
                return                     # a poll from before our choice landed
            self._sent = None
        if pref != self.pref:
            self.apply(pref)
