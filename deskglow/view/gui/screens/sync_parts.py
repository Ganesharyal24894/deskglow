"""The Sync screen's two cards."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, icons, paint
from ..vm import sync as vm
from ..widgets.base import Button, Text
from ..widgets.controls import Segmented, Slider
from ..widgets.glow import shadow
from ..widgets.meters import LevelMeter, MonitorDiagram
from .common import card, h2, small
from .sidebar import Glyph


class LiveSwatch(QWidget):
    """14px rounded square in the live screen colour, glowing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.colour = "#4A7BFF"

    def set_colour(self, colour):
        self.colour = colour
        shadow(self, 10, colour)
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        paint.box(p, self.rect(), 4, self.colour)
        p.end()


def _header(icon, title):
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(Glyph(icon, "text", 20))
    row.addWidget(h2(title, 17), 1)
    return row


def _labelled(label, widget, gap=8):
    col = QVBoxLayout()
    col.setSpacing(gap)
    col.addWidget(small(label))
    col.addWidget(widget)
    return col


def screen_card():
    c, lay = card(22, 18)
    head = _header(icons.SYNC, "Screen sync")
    live = QWidget()
    live_row = QHBoxLayout(live)
    live_row.setContentsMargins(0, 0, 0, 0)
    live_row.setSpacing(8)
    swatch = LiveSwatch()
    live_row.addWidget(swatch)
    live_text = Text("", fonts.mono(12), "muted")
    live_row.addWidget(live_text)
    head.addWidget(live)
    lay.addLayout(head)
    diagram = MonitorDiagram()
    lay.addWidget(diagram)
    chips = Segmented(vm.targets({}), "focus", style="chips", height=36)
    lay.addLayout(_labelled("Which screen", chips))
    styles = Segmented(vm.STYLES, "vivid", equal=True)
    col = _labelled("Colour style", styles)
    desc = Text(vm.STYLE_DESCS["vivid"], fonts.sans(13), "muted", wrap=True)
    col.addWidget(desc)
    lay.addLayout(col)
    lay.addStretch(1)
    start = Button("Start screen sync", "primary", 46, 12, fonts.sans(14, 600))
    lay.addWidget(start)
    return c, {"live": live, "swatch": swatch, "live_text": live_text, "diagram": diagram,
               "chips": chips, "styles": styles, "desc": desc, "start": start}


def music_card():
    c, lay = card(22, 18)
    lay.addLayout(_header(icons.MUSIC, "Music"))
    meter = LevelMeter()
    lay.addWidget(meter)
    sources = Segmented(vm.SOURCES, "system", equal=True)
    lay.addLayout(_labelled("Listen to", sources))
    sens = Slider(1, 100, 60)
    lay.addLayout(_labelled("Sensitivity", sens))
    lay.addStretch(1)
    start = Button("Start music sync", "raised", 46, 12, fonts.sans(14, 600))
    lay.addWidget(start)
    return c, {"meter": meter, "sources": sources, "sens": sens, "start": start}

