"""Selectable tiles: navigation items, mode tiles, effect tiles."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QFontMetricsF, QLinearGradient, QPainterPath
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from .. import fonts, icons, paint
from .base import token

TOP_LEFT_WRAP = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap


def gradient_bar(p, rect, stops):
    """A pill filled with a horizontal gradient; stops may name palette tokens."""
    g = QLinearGradient(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
    for pos, colour in stops:
        g.setColorAt(max(0.0, min(1.0, pos)),
                     paint.qcolor(colour if colour.startswith("#") else token(colour)))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(rect), rect.height() / 2, rect.height() / 2)
    p.restore()


class _Tile(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.update()


class NavItem(_Tile):
    """Sidebar link: icon + label; the active one gets an accent edge."""

    def __init__(self, page_id, label, icon, parent=None):
        super().__init__(parent)
        self.page_id, self.icon = page_id, icon
        self.setText(label)
        self.setFixedHeight(44)
        self.setFont(fonts.sans(14, 500))

    def paintEvent(self, _e):
        p = paint.begin(self)
        r = QRectF(self.rect())
        colour = token("strong" if self.active else "muted")
        if self.active:
            paint.box(p, r, 10, token("raised"))
            clip = QPainterPath()
            clip.addRoundedRect(r, 10, 10)
            p.setClipPath(clip)
            paint.box(p, QRectF(0, 0, 3, r.height()), 0, token("accent_ink"))
            p.setClipping(False)
        icons.draw(p, 12, 13, 18, self.icon, colour)
        paint.text(p, QRectF(42, 0, r.width() - 42, r.height()), self.text(), self.font(), colour)
        p.end()


class ModeTile(_Tile):
    """Home's mode tiles: icon, name, one-line description."""

    def __init__(self, tile, parent=None):
        super().__init__(parent)
        self.tile_id, self.icon, self.desc = tile.id, getattr(icons, tile.icon), tile.desc
        self.setText(tile.label)
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _e):
        p = paint.begin(self)
        r = QRectF(self.rect())
        if self.active:
            paint.box(p, r, 14, token("tile_active"), token("accent_ink"))
        else:
            paint.box(p, r, 14, token("tile"), token("card_border"))
        icons.draw(p, 15, 15, 22, self.icon, token("accent_ink" if self.active else "muted"))
        title = fonts.sans(14, 600)
        y = 15 + 22 + 6
        th = QFontMetricsF(title).height()
        paint.text(p, QRectF(15, y, r.width() - 30, th), self.text(), title, token("text"),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        small = fonts.sans(12)
        paint.text(p, QRectF(15, y + th + 6, r.width() - 30, r.height() - y - th - 6),
                   self.desc, small, token("muted"), TOP_LEFT_WRAP)
        p.end()


class EffectTile(_Tile):
    """An effect: gradient preview over its name."""

    def __init__(self, effect, parent=None):
        super().__init__(parent)
        self.effect = effect
        self.setText(effect.label)
        self.setFixedHeight(62)
        self.setFont(fonts.sans(13, 500))

    def paintEvent(self, _e):
        p = paint.begin(self)
        r = QRectF(self.rect())
        if self.active:
            paint.box(p, r, 12, token("tile_active"), token("accent_ink"))
        else:
            paint.box(p, r, 12, token("card"), token("card_border"))
        th = QFontMetricsF(self.font()).height()
        top = (r.height() - (10 + 10 + th)) / 2
        gradient_bar(p, QRectF(15, top, r.width() - 30, 10), self.effect.stops)
        paint.text(p, QRectF(15, top + 20, r.width() - 30, th), self.text(), self.font(),
                   token("text"), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        p.end()
