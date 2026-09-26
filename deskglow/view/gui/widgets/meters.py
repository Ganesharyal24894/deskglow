"""Readouts: the focus ring, the monitor diagram, the level meter, signal bars."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QWidget

from .. import fonts, paint
from .base import token


class FocusRing(QWidget):
    """300x300 ring: track plus an arc for the time remaining, glowing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)
        self.fraction, self.colour = 1.0, "#28A0C8"

    def set_ring(self, fraction, colour):
        self.fraction, self.colour = fraction, colour
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        box = QRectF(20, 20, 260, 260)
        p.setPen(QPen(paint.qcolor(token("ring_track")), 14))
        p.drawEllipse(box)
        if self.fraction > 0:
            span = -int(360 * 16 * self.fraction)      # clockwise from 12 o'clock
            for width, alpha in ((34, 0.10), (28, 0.14), (22, 0.2), (18, 0.28)):
                pen = QPen(paint.qcolor(self.colour, alpha * 0.55 / 0.28 * 0.5), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(box, 90 * 16, span)
            pen = QPen(paint.qcolor(self.colour), 14)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(box, 90 * 16, span)
        p.end()


class MonitorDiagram(QWidget):
    """Screens side by side, bottom-aligned, in a dark well. Click one to pick it."""

    picked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(128)
        self.boxes, self.lit, self.glow_colour = [], set(), "#4A7BFF"
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_state(self, boxes, lit, glow_colour):
        self.boxes, self.lit, self.glow_colour = boxes, set(lit), glow_colour
        self.update()

    def rects(self):
        total = sum(b.width for b in self.boxes) + 12 * max(0, len(self.boxes) - 1)
        x = (self.width() - total) / 2.0
        out = []
        for b in self.boxes:
            out.append((b, QRectF(x, self.height() - 12 - b.height, b.width, b.height)))
            x += b.width + 12
        return out

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 14, token("inset"))
        if not self.boxes:
            paint.text(p, self.rect(), "No screens found", fonts.sans(13), token("muted"),
                       Qt.AlignmentFlag.AlignCenter)
        for b, r in self.rects():
            on = b.name in self.lit
            if on:
                paint.glow(p, r, 8, self.glow_colour, 0.35, 20, 0)
            paint.box(p, r, 8, token("monitor"), token("accent_ink" if on else "control_border"), 2.0)
            name_f, res_f = fonts.sans(12, 600), fonts.sans(11)
            mid = r.center().y()
            paint.text(p, QRectF(r.left(), mid - 16, r.width(), 16), b.name, name_f,
                       token("text"), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            paint.text(p, QRectF(r.left(), mid + 1, r.width(), 15), b.resolution, res_f,
                       token("muted"), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        p.end()

    def mousePressEvent(self, e):
        for b, r in self.rects():
            if r.contains(e.position()):
                self.picked.emit(b.name)
                return


class LevelMeter(QWidget):
    """Eighteen bars in a well; heights are fractions 0..1."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(128)
        self.heights = [0.06] * 18

    def set_heights(self, heights):
        self.heights = list(heights)
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 14, token("inset"))
        n = len(self.heights)
        inner = QRectF(self.rect()).adjusted(14, 12, -14, -12)
        w = (inner.width() - 5 * (n - 1)) / n
        for i, h in enumerate(self.heights):
            bh = inner.height() * h
            p.setOpacity(0.35 + h * 100 / 160.0)
            paint.box(p, QRectF(inner.left() + i * (w + 5), inner.bottom() - bh, w, bh), 3,
                      token("accent_ink"))
        p.end()


class SignalBars(QWidget):
    """Four rising bars, `level` of them lit."""

    def __init__(self, level=0, parent=None):
        super().__init__(parent)
        self.level = level
        self.setFixedSize(25, 18)

    def paintEvent(self, _e):
        p = paint.begin(self)
        for n in range(1, 5):
            h = n * 4 + 2
            colour = token("text" if n <= self.level else "bar_off")
            paint.box(p, QRectF((n - 1) * 7, 18 - h, 4, h), 2, colour)
        p.end()
