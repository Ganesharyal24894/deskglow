"""Colour pickers: the swatch grid and the hue ring."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QConicalGradient
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QMenu, QWidget

from .. import paint
from ..theme import DEFAULT_ACCENT
from ..vm import hue
from .base import token


class SwatchButton(QAbstractButton):
    def __init__(self, colour, name, height=44, inset_ring=True, parent=None):
        super().__init__(parent)
        self.colour, self.selected, self.inset_ring = colour, False, inset_ring
        self.setToolTip(name)
        self.setAccessibleName(name)
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = paint.begin(self)
        if self.selected:
            paint.box(p, self.rect(), 12, self.colour, token("swatch_ring"), 2.0)
            if self.inset_ring:                           # inset 0 0 0 3px ring
                inner = QRectF(self.rect()).adjusted(2, 2, -2, -2)
                paint.box(p, inner, 10, None, token("bg"), 3.0)
        else:
            paint.box(p, self.rect(), 12, self.colour, token("control_border"))
        p.end()


class SwatchGrid(QWidget):
    """Four columns of favourites. `picked(hex)`; right-click offers removal."""

    picked = Signal(str)
    remove = Signal(str)

    def __init__(self, gap=10, height=44, inset_ring=True, parent=None):
        super().__init__(parent)
        self.cell_height, self.inset_ring = height, inset_ring
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(gap)
        self.buttons = []

    def set_swatches(self, swatches):
        """swatches: [vm.home.Swatch]; rebuilds only when the colours change."""
        if [b.colour for b in self.buttons] != [s.colour for s in swatches]:
            for b in self.buttons:
                self.grid.removeWidget(b)
                b.deleteLater()
            self.buttons = []
            for i, s in enumerate(swatches):
                b = SwatchButton(s.colour, s.name, self.cell_height, self.inset_ring, self)
                b.clicked.connect(lambda _c=False, c=s.colour: self.picked.emit(c))
                b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                b.customContextMenuRequested.connect(lambda _pos, btn=b: self._menu(btn))
                self.grid.addWidget(b, i // 4, i % 4)
                self.buttons.append(b)
            for col in range(4):
                self.grid.setColumnStretch(col, 1)
        for b, s in zip(self.buttons, swatches, strict=True):
            if b.selected != s.selected:
                b.selected = s.selected
                b.update()

    def _menu(self, button):
        menu = QMenu(self)
        menu.addAction("Remove from favourites", lambda: self.remove.emit(button.colour))
        menu.popup(button.mapToGlobal(button.rect().center()))


class HueRing(QWidget):
    """The 128px conic ring: click/drag on the band picks that colour."""

    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(128, 128)
        self.colour, self.glow = DEFAULT_ACCENT, 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_colour(self, colour, glow):
        self.colour, self.glow = colour, glow
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        g = QConicalGradient(QPointF(64, 64), 90.0)
        n = len(hue.CONIC) - 1
        for i, c in enumerate(hue.CONIC):     # CSS runs clockwise from 12 o'clock
            g.setColorAt(1.0 - i / n, paint.qcolor(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QRectF(0, 0, 128, 128))
        paint.box(p, QRectF(22, 22, 84, 84), 42, token("card"))
        dot = QRectF(38, 38, 52, 52)
        paint.glow(p, dot, 26, self.colour, self.glow, 18, 2)
        paint.box(p, dot, 26, self.colour)
        dx, dy = hue.marker_centre(hue.angle_for(self.colour))
        paint.box(p, QRectF(64 + dx - 8, 64 + dy - 8, 16, 16), 8, None, token("strong"), 3.0)
        p.end()

    def _pick(self, pos):
        dx, dy = pos.x() - 64, pos.y() - 64
        if hue.on_band(dx, dy):
            self.picked.emit(hue.colour_at(hue.angle_of(dx, dy)))

    def mousePressEvent(self, e):
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._pick(e.position())
