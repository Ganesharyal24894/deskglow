"""The shared sidebar: logo, navigation, the Dark mode switch, and the
strip's connection card."""
from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, icons, paint, theme
from ..widgets.base import Card, Text, token
from ..widgets.controls import Toggle
from ..widgets.glow import BrandMark
from ..widgets.tiles import NavItem

PAGES = (("home", "Home", icons.HOME), ("effects", "Effects", icons.EFFECTS),
         ("sync", "Sync", icons.SYNC), ("focus", "Focus", icons.FOCUS),
         ("settings", "Settings", icons.SETTINGS))


class Dot(QWidget):
    def __init__(self, colour="ok", size=8, parent=None):
        super().__init__(parent)
        self.colour = colour
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), self.width() / 2, token(self.colour))
        p.end()


class Glyph(QWidget):
    """A fixed-size icon."""

    def __init__(self, markup, colour="muted", size=16, parent=None):
        super().__init__(parent)
        self.markup, self.colour = markup, colour
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        p = paint.begin(self)
        icons.draw(p, 0, 0, self.width(), self.markup, token(self.colour))
        p.end()


class DarkModeRow(QWidget):
    """Moon (dark) / sun (light) icon, "Dark mode", and a 44x26 switch showing
    the theme on screen. Clicking asks `flip` to switch."""

    def __init__(self, flip=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 6, 0)
        row.setSpacing(10)
        self.icon = Glyph(icons.MOON, "muted", 18)
        row.addWidget(self.icon)
        row.addWidget(Text("Dark mode", fonts.sans(14, 500), "muted"), 1)
        self.switch = Toggle(width=44, height=26)
        self.switch.setAccessibleName("Dark mode")
        row.addWidget(self.switch)
        if flip is not None:
            self.switch.clicked.connect(lambda _on: flip())
        self.apply_theme()

    def apply_theme(self):
        dark = theme.current().name == "dark"
        self.switch.setChecked(dark)
        self.icon.markup = icons.MOON if dark else icons.SUN
        self.icon.update()
        self.switch.update()


class DeviceCard(Card):
    def __init__(self, parent=None):
        super().__init__(radius=14, parent=parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(15, 15, 15, 15)
        col.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(Glyph(icons.BLUETOOTH))
        self.name = Text("Desk strip", fonts.sans(13, 600))
        top.addWidget(self.name, 1)
        col.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.dot = Dot()
        row.addWidget(self.dot)
        self.state = Text("Connected", fonts.sans(12), "muted")
        row.addWidget(self.state)
        row.addStretch(1)
        self.rssi = Text("", fonts.mono(12), "muted")
        row.addWidget(self.rssi)
        col.addLayout(row)

    def show_status(self, status):
        self.name.setText(status.name)
        text, dot = status.connection()
        self.state.setText(text)
        self.dot.colour = dot
        self.dot.update()
        self.rssi.setText(status.rssi_text())


class Sidebar(QWidget):
    picked = Signal(str)

    def __init__(self, theme_switch=None, parent=None):
        super().__init__(parent)
        self.setFixedWidth(216)
        col = QVBoxLayout(self)
        col.setContentsMargins(14, 24, 15, 16)
        col.setSpacing(28)
        brand = QHBoxLayout()
        brand.setContentsMargins(10, 0, 10, 0)
        self.brand = BrandMark()
        brand.addWidget(self.brand)
        col.addLayout(brand)
        nav = QVBoxLayout()
        nav.setSpacing(2)                   # 4px gaps: each NavItem has 2px shadow room
        self.items = {}
        for pid, label, icon in PAGES:
            item = NavItem(pid, label, icon)
            item.clicked.connect(lambda _c=False, p=pid: self.picked.emit(p))
            nav.addWidget(item)
            self.items[pid] = item
        col.addLayout(nav)
        col.addStretch(1)
        bottom = QVBoxLayout()
        bottom.setSpacing(10)
        self.dark_mode = DarkModeRow(theme_switch.flip if theme_switch is not None else None)
        bottom.addWidget(self.dark_mode)
        self.card = DeviceCard()
        bottom.addWidget(self.card)
        col.addLayout(bottom)
        if theme_switch is not None:
            theme_switch.changed.connect(self.dark_mode.apply_theme)

    def set_active(self, page_id):
        for pid, item in self.items.items():
            item.set_active(pid == page_id)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 0, token("side"))
        paint.box(p, QRectF(self.width() - 1, 0, 1, self.height()), 0, token("rule"))
        p.end()
