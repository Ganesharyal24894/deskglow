"""Effects: the preset's built-in effects as tiles, a filter, and the
"Playing" bar with the speed slider."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ....model.presets import get_preset
from .. import fonts, paint, theme
from ..throttle import Throttle
from ..vm import effects as vm
from ..widgets.base import Text, token
from ..widgets.controls import Segmented, Slider
from ..widgets.tiles import EffectTile, gradient_bar
from .common import Page, card, title_block


class PreviewBar(QWidget):
    """The 120x14 preview in the Playing bar, with a faint white glow (dark only)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 34)
        self.stops = ()

    def paintEvent(self, _e):
        p = paint.begin(self)
        r = QRectF(10, 10, 120, 14)
        paint.glow(p, r, 7, token("preview_glow"), theme.current().preview_glow_alpha, 18, 0)
        if self.stops:
            gradient_bar(p, r, self.stops)
        p.end()


class EffectsPage(Page):
    def __init__(self, ctx, preset=None, parent=None):
        super().__init__(16, parent)
        self.ctx = ctx
        self.all = vm.effects((preset or get_preset()).effect_names())
        self.filter = "all"
        self.selected = (preset or get_preset()).default_effect
        head = QHBoxLayout()
        head.setSpacing(16)
        titles, _t, _s = title_block(
            "Effects", "Run on the strip's own controller, so they stay smooth with no PC load.")
        head.addLayout(titles, 1)
        self.filters = Segmented(vm.FILTERS, "all", well="filter_well", well_border="card_border")
        head.addWidget(self.filters, 0, Qt.AlignmentFlag.AlignBottom)
        self.body.addLayout(head)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)
        self.tiles = {e.id: EffectTile(e) for e in self.all}
        for tile in self.tiles.values():
            tile.clicked.connect(lambda _c=False, t=tile: self._play(t.effect.id))
        self._layout_tiles()
        self.body.addWidget(self.grid_host)
        self.body.addStretch(1)

        bar, lay = card(0, 18, 16, horizontal=True)
        bar.setFixedHeight(72)
        lay.setContentsMargins(11, 0, 21, 0)
        lay.setSpacing(0)
        self.preview = PreviewBar()
        lay.addWidget(self.preview)
        lay.addSpacing(8)             # 18px after the bar; its glow margin is 10
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.playing = Text("Playing", fonts.sans(12), "muted")
        self.now = Text("", fonts.sans(14, 600))
        col.addStretch(1)
        col.addWidget(self.playing)
        col.addWidget(self.now)
        col.addStretch(1)
        holder = QWidget()
        holder.setFixedWidth(170)
        holder.setLayout(col)
        lay.addWidget(holder)
        lay.addSpacing(18)
        lay.addWidget(Text("Speed", fonts.sans(13), "muted"))
        lay.addSpacing(18)
        self.speed = Slider(1, 100, 50)
        lay.addWidget(self.speed, 1)
        lay.addSpacing(18)
        self.speed_value = Text("50", fonts.display(16, 600))
        self.speed_value.setFixedWidth(48)
        self.speed_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.speed_value)
        self.body.addWidget(bar)

        self._send_speed = Throttle(self._speed_changed, 200, self)
        self.speed.valueChanged.connect(lambda v: self.speed_value.setText(str(v)))
        self.speed.valueChanged.connect(self._send_speed)
        self.filters.picked.connect(self.set_filter)
        ctx.status_changed.connect(self.show_status)
        self._refresh_selection(False)

    def _layout_tiles(self):
        for tile in self.tiles.values():
            self.grid.removeWidget(tile)
            tile.hide()
        for i, e in enumerate(vm.visible(self.all, self.filter)):
            tile = self.tiles[e.id]
            self.grid.addWidget(tile, i // 4, i % 4)
            tile.show()
        for col in range(4):
            self.grid.setColumnStretch(col, 1)

    def set_filter(self, filter_id):
        self.filter = filter_id
        self.filters.set_current(filter_id)
        self._layout_tiles()

    def _play(self, effect_id):
        self.selected = effect_id
        self._refresh_selection(True)
        self.ctx.send(vm.play(effect_id, self.speed.value()))

    def _speed_changed(self, value):
        if self.ctx.status.mode == "pattern":
            self.ctx.send(vm.play(self.selected, value))

    def _refresh_selection(self, playing):
        for eid, tile in self.tiles.items():
            tile.set_active(eid == self.selected)
        effect = next((e for e in self.all if e.id == self.selected), None)
        self.preview.stops = effect.stops if effect else ()
        self.preview.update()
        self.now.setText(effect.label if effect else "")
        self.playing.setText("Playing" if playing else "Not playing")

    def show_status(self, s):
        playing = s.mode == "pattern" and s.args.get("name") in self.tiles
        if playing:
            self.selected = s.args["name"]
            self.speed.set_quietly(int(s.args.get("speed", 50)))
            if not self.speed.isSliderDown():
                self.speed_value.setText(str(self.speed.value()))
        self._refresh_selection(playing)
