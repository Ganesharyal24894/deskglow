"""Layout helpers the screens share: page scaffold, headings, card columns."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts
from ..widgets.base import Card, Text


def h1(text):
    return Text(text, fonts.display(26, 600, -0.02))


def h2(text, px=15):
    return Text(text, fonts.display(px, 600))


def subtitle(text):
    return Text(text, fonts.sans(14), "muted")


def small(text, colour="muted"):
    return Text(text, fonts.sans(13), colour)


class Page(QWidget):
    """A main-area page: 28px/32px padding, vertical flow with `gap`."""

    def __init__(self, gap=20, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(32, 28, 32, 28)
        self.body.setSpacing(gap)


def title_block(title, sub=None):
    """h1 over an optional muted line (gap 2)."""
    box = QVBoxLayout()
    box.setSpacing(2)
    t = h1(title)
    box.addWidget(t)
    s = None
    if sub is not None:
        s = subtitle(sub)
        box.addWidget(s)
    return box, t, s


def card(pad=20, gap=14, radius=20, horizontal=False):
    """(Card, its layout) with CSS-like padding (the 1px border included)."""
    c = Card(radius=radius)
    lay = QHBoxLayout(c) if horizontal else QVBoxLayout(c)
    lay.setContentsMargins(pad + 1, pad + 1, pad + 1, pad + 1)
    lay.setSpacing(gap)
    return c, lay


def row(spacing=10, *widgets, stretch_at=None):
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for i, w in enumerate(widgets):
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w, 1 if i == stretch_at else 0)
    return lay
