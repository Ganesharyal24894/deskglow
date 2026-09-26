"""The shared sidebar: logo, navigation, and the strip's connection card."""
from PySide6.QtCore import QRectF, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, icons, paint
from ..widgets.base import Card, Text, token
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

    def __init__(self, parent=None):
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
        nav.setSpacing(4)
        self.items = {}
        for pid, label, icon in PAGES:
            item = NavItem(pid, label, icon)
            item.clicked.connect(lambda _c=False, p=pid: self.picked.emit(p))
            nav.addWidget(item)
            self.items[pid] = item
        col.addLayout(nav)
        col.addStretch(1)
        self.card = DeviceCard()
        col.addWidget(self.card)

    def set_active(self, page_id):
        for pid, item in self.items.items():
            item.set_active(pid == page_id)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 0, token("bg"))
        paint.box(p, QRectF(self.width() - 1, 0, 1, self.height()), 0, token("rule"))
        p.end()
