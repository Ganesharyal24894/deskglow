"""Home's cards: the strip preview row, Colour, and Modes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget

from .. import fonts, icons
from ..theme import DEFAULT_ACCENT
from ..vm import home as vm
from ..widgets.base import Button, Text
from ..widgets.colour import HueRing, SwatchGrid
from ..widgets.controls import Slider
from ..widgets.tiles import ModeTile
from .common import card, h2
from .sidebar import Glyph


class BrightnessRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(16)
        lay.addWidget(Glyph(icons.SUN, "stage_muted", 18))
        label = Text("Brightness", fonts.sans(13), "stage_muted")
        label.setFixedWidth(74)
        lay.addWidget(label)
        self.slider = Slider(0, 100, 80)
        self.slider.setObjectName("stage")
        lay.addWidget(self.slider, 1)
        self.value = Text("80%", fonts.display(18, 600), "stage_text")
        self.value.setFixedWidth(52)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.value)
        self.slider.valueChanged.connect(lambda v: self.value.setText(f"{v}%"))

    def set_value(self, value):
        self.slider.set_quietly(value)
        if not self.slider.isSliderDown():
            self.value.setText(f"{int(value)}%")


def colour_card():
    """(card, parts) — parts: hex, ring, swatches, save."""
    c, lay = card(20, 16)
    c.setFixedWidth(340)
    head = QHBoxLayout()
    head.addWidget(h2("Colour"), 1)
    hexl = Text(DEFAULT_ACCENT, fonts.mono(13), "muted")
    head.addWidget(hexl)
    lay.addLayout(head)
    mid = QHBoxLayout()
    mid.setSpacing(18)
    ring = HueRing()
    mid.addWidget(ring, 0, Qt.AlignmentFlag.AlignVCenter)
    swatches = SwatchGrid()
    mid.addWidget(swatches, 1, Qt.AlignmentFlag.AlignVCenter)
    lay.addLayout(mid)
    save = Button("Save as favourite", "raised", 44, 12, icon=icons.PLUS)
    save.icon_stroke = 1.8
    lay.addWidget(save)
    lay.addStretch(1)
    return c, {"hex": hexl, "ring": ring, "swatches": swatches, "save": save}


def modes_card():
    """(card, {tile_id: ModeTile})."""
    c, lay = card(20, 14)
    lay.addWidget(h2("Modes"))
    grid = QGridLayout()
    grid.setSpacing(10)
    tiles = {}
    for i, tile in enumerate(vm.MODE_TILES):
        t = ModeTile(tile)
        grid.addWidget(t, i // 3, i % 3)
        tiles[tile.id] = t
    for col in range(3):
        grid.setColumnStretch(col, 1)
    lay.addLayout(grid, 1)
    return c, tiles
