"""The system tray icon: a click opens the quick panel; the menu has Open,
power and Quit. Without a system tray the app simply has no tray."""
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import paint
from .accent import accent
from .vm import home as home_vm
from .vm import tray as vm


def tray_icon_pixmap(colour, size=32):
    """The logo bar on transparent: a glowing pill in the accent colour."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bar = QRectF(size * 0.12, size * 0.4, size * 0.76, size * 0.22)
    paint.glow(p, bar, bar.height() / 2, colour, 0.7, size * 0.18, 0)
    paint.box(p, bar, bar.height() / 2, colour)
    p.end()
    return pix


def place_popup(panel, anchor, screen_rect):
    """Top-left for a panel near `anchor` (the tray icon rect), kept on screen."""
    w, h = panel.width(), panel.height()
    x = anchor.center().x() - w // 2
    y = anchor.top() - h - 8 if anchor.center().y() > screen_rect.center().y() \
        else anchor.bottom() + 8
    x = max(screen_rect.left() + 8, min(x, screen_rect.right() - w - 8))
    y = max(screen_rect.top() + 8, min(y, screen_rect.bottom() - h - 8))
    return QPoint(x, y)


class Tray:
    def __init__(self, ctx, panel, show_window, quit_app):
        self.ctx, self.panel = ctx, panel
        self.show_window, self.quit_app = show_window, quit_app
        self.icon = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            ctx.set_tray_available(False)
            return
        self.icon = QSystemTrayIcon(QIcon(tray_icon_pixmap(accent())))
        self.icon.setToolTip("Deskglow")
        self.menu = QMenu()
        self.menu.addAction("Open Deskglow", show_window)
        self.power_action = self.menu.addAction("Turn off", self.toggle_power)
        self.menu.addSeparator()
        self.menu.addAction("Quit", quit_app)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        panel.open_app.connect(self._open_from_panel)
        panel.quit_app.connect(quit_app)
        ctx.status_changed.connect(self.show_status)
        self.icon.show()
        ctx.set_tray_available(True)

    def toggle_power(self):
        self.ctx.send(home_vm.power(self.ctx.status))

    def _open_from_panel(self):
        self.panel.hide()
        self.show_window()

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_panel()

    def toggle_panel(self):
        if self.panel.isVisible():
            self.panel.hide()
            return
        anchor = self.icon.geometry() if self.icon is not None else QRect()
        if anchor.isEmpty():
            anchor = QRect(QCursor.pos(), QCursor.pos())
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        self.panel.move(place_popup(self.panel, anchor, screen.availableGeometry()))
        self.panel.show()
        self.panel.raise_()

    def show_status(self, s):
        self.power_action.setText(vm.menu_power_label(s))
        if accent() != getattr(self, "_icon_colour", None):
            self._icon_colour = accent()
            self.icon.setIcon(QIcon(tray_icon_pixmap(self._icon_colour)))

    def hide(self):
        if self.icon is not None:
            self.icon.hide()
