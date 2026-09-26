"""Text, cards and buttons, painted from the palette so a theme switch or an
accent change only needs a repaint."""
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from .. import fonts, icons, paint, theme
from ..accent import accent


def token(name):
    """A palette colour by token name, the accent for "accent", or a literal #hex.
    A palette value that names another token is followed."""
    if name.startswith("#"):
        return name
    if name == "accent":
        return accent()
    if name == "accent_ink":
        return theme.ink(accent(), theme.current().ink_scale)
    return token(getattr(theme.current(), name))


class Text(QLabel):
    """A label whose colour is a palette token, re-read on apply_theme()."""

    def __init__(self, text="", font=None, colour="text", wrap=False, parent=None):
        super().__init__(text, parent)
        self.setFont(font or fonts.sans(14))
        self.colour = colour
        self.setWordWrap(wrap)
        self.apply_theme()

    def set_colour(self, colour):
        self.colour = colour
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(f"color: {token(self.colour)}; background: transparent;")


class Card(QWidget):
    """A rounded surface (the design's <section> cards)."""

    def __init__(self, radius=20, fill="card", border="card_border", parent=None):
        super().__init__(parent)
        self.radius, self.fill, self.border = radius, fill, border

    def paintEvent(self, _event):
        p = paint.begin(self)
        paint.box(p, self.rect(), self.radius, token(self.fill),
                  token(self.border) if self.border else None)
        p.end()


# kind -> (fill token or None, border token or None, text token)
KINDS = {
    "raised": ("raised", "control_border", "text"),
    "ghost": (None, "control_border", "muted"),
    "outline": (None, "control_border", "text"),
    "primary": ("accent", "primary_border", "on_accent"),
    "danger": (None, "danger_border", "danger_text"),
    "link": (None, None, "muted"),
    "plain": (None, None, "text"),
}


class Button(QAbstractButton):
    """A button drawn like the design's: filled/outlined box, optional icon."""

    def __init__(self, text="", kind="raised", height=44, radius=12, font=None,
                 icon=None, icon_size=16, pad=16, min_width=0, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.kind, self.radius, self.pad, self.min_width = kind, radius, pad, min_width
        self.icon_markup, self.icon_size, self.icon_stroke = icon, icon_size, 1.8
        self.fill_override = self.text_override = self.border_override = None
        self.setFont(font or fonts.sans(14, 500))
        self.setFixedHeight(height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def colours(self):
        fill, border, text = KINDS[self.kind]
        fill = self.fill_override or fill
        border = self.border_override or border
        return (token(fill) if fill else None, token(border) if border else None,
                token(self.text_override or text))

    def sizeHint(self):
        fm = QFontMetricsF(self.font())
        w = fm.horizontalAdvance(self.text()) + 2 * self.pad
        if self.icon_markup:
            w += self.icon_size + (8 if self.text() else 0)
        return QSize(max(self.min_width, int(w + 1)), self.height())

    def paintEvent(self, _event):
        p = paint.begin(self)
        if not self.isEnabled():
            p.setOpacity(0.4)
        fill, border, text = self.colours()
        if self.underMouse() and self.isEnabled() and self.kind != "link":
            fill = paint.qcolor(fill).lighter(112).name() if fill else token("raised")
        if self.kind not in ("link", "plain"):
            paint.box(p, self.rect(), self.radius, fill, border)
        f = self.font()
        f.setUnderline(self.kind == "link")
        fm = QFontMetricsF(f)
        tw = fm.horizontalAdvance(self.text())
        gap = 8 if self.icon_markup and self.text() else 0
        iw = self.icon_size if self.icon_markup else 0
        x = (self.width() - tw - iw - gap) / 2.0
        if self.icon_markup:
            icons.draw(p, x, (self.height() - iw) / 2.0, iw, self.icon_markup, text,
                       self.icon_stroke)
        paint.text(p, QRectF(x + iw + gap, 0, tw + 2, self.height()), self.text(), f, text)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)
