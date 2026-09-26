"""Switch, segmented control / chip group, and the slider."""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QAbstractButton, QSlider, QWidget

from .. import fonts, paint, theme
from .base import token


class Toggle(QAbstractButton):
    """The design's switch: 48x28 (44x26 in the sidebar), accent_ink when on."""

    def __init__(self, parent=None, width=48, height=28):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = paint.begin(self)
        if not self.isEnabled():
            p.setOpacity(0.4)
        on = self.isChecked()
        w, h = self.width(), self.height()
        paint.box(p, self.rect(), h / 2, token("accent_ink" if on else "control_border"))
        k = h - 6
        knob = QRectF(w - 3 - k if on else 3, 3, k, k)
        paint.glow(p, knob.translated(0, 1), k / 2, "#000000", 0.25, 2)   # 0 1px 2px
        paint.box(p, knob, k / 2, token("knob_on" if on else "knob_off"))
        p.end()


class Segmented(QWidget):
    """A row of mutually exclusive options, painted in one widget.

    style="segmented": options inside a well; selected option filled.
    style="chips": outlined pills that wrap; selected pill outlined in accent.
    equal=True gives every option the same width (a CSS grid)."""

    picked = Signal(str)

    def __init__(self, options, current=None, style="segmented", well="inset", well_border=None,
                 height=36, radius=9, well_radius=12, pad=14, gap=4, inset=4, equal=False,
                 font=None, parent=None):
        super().__init__(parent)
        self.options = list(options)
        self.current = current if current is not None else (self.options[0][0] if self.options else None)
        self.style, self.well, self.well_border = style, well, well_border
        self.h, self.radius, self.well_radius = height, radius, well_radius
        self.pad, self.gap, self.inset, self.equal = pad, gap, inset, equal
        self.setFont(font or fonts.sans(13, 500))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if style == "chips":
            self.inset, self.gap = 0, gap if gap != 4 else 6
        policy = self.sizePolicy()
        policy.setVerticalPolicy(policy.Policy.Fixed)
        self.setSizePolicy(policy)
        self.setMinimumHeight(self.heightForWidth(10000))
        if style != "chips" and not equal:
            self.setMinimumWidth(self.sizeHint().width())     # never clip an option

    def set_options(self, options, current=None):
        self.options = list(options)
        if current is not None:
            self.current = current
        self.updateGeometry()
        self.setMinimumHeight(self.heightForWidth(max(1, self.width())))
        self.update()

    def set_current(self, option_id):
        if option_id != self.current:
            self.current = option_id
            self.update()

    def _natural(self, label):
        return QFontMetricsF(self.font()).horizontalAdvance(label) + 2 * self.pad

    def rects(self, width=None):
        """{id: QRectF} for each option at the given widget width."""
        width = self.width() if width is None else width
        n = len(self.options)
        if not n:
            return {}
        out, x, y = {}, float(self.inset), float(self.inset)
        if self.equal:
            each = (width - 2 * self.inset - self.gap * (n - 1)) / n
            for i, (oid, _label) in enumerate(self.options):
                out[oid] = QRectF(self.inset + i * (each + self.gap), self.inset, each, self.h)
            return out
        for oid, label in self.options:
            w = self._natural(label)
            if self.style == "chips" and x > 0 and x + w > width:
                x, y = 0.0, y + self.h + self.gap
            out[oid] = QRectF(x, y, w, self.h)
            x += w + self.gap
        return out

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        rects = self.rects(width)
        bottom = max((r.bottom() for r in rects.values()), default=0.0)
        return int(bottom + self.inset + 0.5)

    def sizeHint(self):
        rects = self.rects(10000)
        right = max((r.right() for r in rects.values()), default=0.0)
        return QSize(int(right + self.inset + 0.5), self.heightForWidth(10000))

    def resizeEvent(self, e):
        self.setMinimumHeight(self.heightForWidth(self.width()))
        super().resizeEvent(e)

    def paintEvent(self, _e):
        p = paint.begin(self)
        if self.style != "chips":
            used = self.rects()
            right = self.width() if self.equal else max(r.right() for r in used.values()) + self.inset
            paint.box(p, QRectF(0, 0, right, self.heightForWidth(self.width())), self.well_radius,
                      token(self.well),
                      token(self.well_border) if self.well_border else None)
        for oid, label in self.options:
            r = self.rects()[oid]
            on = oid == self.current
            if self.style == "chips":
                paint.box(p, r, self.h / 2, token("tile_active") if on else None,
                          token("accent_ink" if on else "control_border"))
            elif on:
                lift = theme.current().seg_shadow
                paint.soft_shadow(p, r, self.radius, theme.SHADOW, lift)
                paint.box(p, r, self.radius, token("seg_on"))
            paint.text(p, r, label, self.font(), token("strong" if on else "muted"),
                       Qt.AlignmentFlag.AlignCenter)
        p.end()

    def mousePressEvent(self, e):
        for oid, r in self.rects().items():
            if r.contains(e.position()):
                if oid != self.current:
                    self.current = oid
                    self.update()
                self.picked.emit(oid)
                return


class Slider(QSlider):
    """A horizontal range input (styled by the app stylesheet)."""

    def __init__(self, lo=0, hi=100, value=0, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(lo, hi)
        self.setValue(value)
        self.setFixedHeight(24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_quietly(self, value):
        """Follow the daemon without emitting, unless the user is dragging."""
        if self.isSliderDown():
            return
        self.blockSignals(True)
        self.setValue(int(value))
        self.blockSignals(False)
