"""Things that glow in the accent colour: the brand bar, the strip preview."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, paint, theme
from ..accent import accent
from .base import Text, token


def shadow(widget, blur, colour=None, alpha=1.0):
    """Give `widget` an outer glow (drawn outside its rect by its parent)."""
    eff = widget.graphicsEffect()
    if not isinstance(eff, QGraphicsDropShadowEffect):
        eff = QGraphicsDropShadowEffect(widget)
        eff.setOffset(0, 0)
        widget.setGraphicsEffect(eff)
    eff.setBlurRadius(blur)
    eff.setColor(paint.qcolor(colour or accent(), alpha))
    eff.setEnabled(alpha > 0)
    return eff


class GlowBar(QWidget):
    """The small accent bar of the logo, glowing."""

    def __init__(self, width=26, height=8, blur=20, colour=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.colour, self.blur = colour, blur
        shadow(self, blur, colour)

    def apply_theme(self):
        shadow(self, self.blur, self.colour)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), self.height() / 2, self.colour or accent())
        p.end()


class BrandMark(QWidget):
    """Bar + "deskglow" wordmark."""

    def __init__(self, size=19, bar=(26, 8), blur=20, colour=None, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.bar = GlowBar(bar[0], bar[1], blur, colour)
        row.addWidget(self.bar)
        row.addWidget(Text("deskglow", fonts.display(size, 600, -0.01 if size == 19 else 0)))
        row.addStretch(1)


class StripPreview(QWidget):
    """The 176px card: a glowing strip at the top, `row` (brightness) at the bottom."""

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.setFixedHeight(176)
        self.on, self.level = True, 80
        lay = QVBoxLayout(self)
        lay.setContentsMargins(33, 29, 33, 29)
        lay.addStretch(1)
        lay.addWidget(row)

    def set_state(self, on, level):
        self.on, self.level = on, level
        self.update()

    def bar_rect(self):
        return QRectF(33, 1 + 28 + 18, self.width() - 66, 14)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 20, token("stage"), token("stage_line"))
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 19, 19)
        p.setClipPath(clip)
        c = accent()
        if self.on:
            opacity = 0.35 + 0.65 * self.level / 100.0
            a = (0.25 + 0.6 * self.level / 100.0) * opacity
            paint.glow(p, self.bar_rect(), 7, c, a, 90, 24)
            paint.glow(p, self.bar_rect(), 7, c, a, 36, 10)
            p.setOpacity(opacity)
            paint.box(p, self.bar_rect(), 7, c)
        else:
            paint.box(p, self.bar_rect(), 7, token("strip_off"))
        p.end()


class TrayStrip(QWidget):
    """The tray panel's 10px strip on its stage (padding: the palette's tray_pad;
    the stage is only visible in light mode). Its glow spills over the
    neighbouring rows, so the panel paints stage and glow underneath."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on = True
        self.apply_theme()

    def apply_theme(self):
        self.setFixedHeight(10 + 2 * theme.current().tray_pad[1])

    def bar_rect(self):
        x, y = theme.current().tray_pad
        return QRectF(x, y, self.width() - 2 * x, 10)

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.bar_rect(), 5, accent() if self.on else token("strip_off"))
        p.end()


def centred(widget, align=Qt.AlignmentFlag.AlignCenter):
    """Wrap a fixed-size widget so it sits centred in a layout cell."""
    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(widget, 0, align)
    return holder
