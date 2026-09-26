"""Home: power, reset, the glowing strip preview, colour and modes."""
from PySide6.QtWidgets import QHBoxLayout

from .. import fonts, icons
from ..throttle import Throttle
from ..vm import home as vm
from ..widgets.base import Button
from ..widgets.glow import StripPreview, shadow
from .common import Page, title_block
from .home_parts import BrightnessRow, colour_card, modes_card


class HomePage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__(20, parent)
        self.ctx = ctx
        self.remembered_effect = None
        head = QHBoxLayout()
        head.setSpacing(16)
        titles, self.title, self.state = title_block("Desk strip", "Off")
        head.addLayout(titles, 1)
        self.reset = Button("Reset", "ghost", 44, 12, icon=icons.RESET)
        head.addWidget(self.reset)
        self.power = Button("On", "primary", 44, 12, fonts.sans(14, 600), icons.POWER, 20, 18, 92)
        self.power.icon_stroke = 2
        self.power.setAccessibleName("Power")
        head.addWidget(self.power)
        self.body.addLayout(head)

        self.bri = BrightnessRow()
        self.preview = StripPreview(self.bri)
        self.body.addWidget(self.preview)

        grid = QHBoxLayout()
        grid.setSpacing(20)
        colour, self.colour = colour_card()
        grid.addWidget(colour)
        modes, self.tiles = modes_card()
        grid.addWidget(modes, 1)
        self.body.addLayout(grid, 1)

        self._send_bri = Throttle(lambda v: ctx.send(vm.brightness(v)), 150, self)
        self._send_colour = Throttle(lambda c: ctx.send(vm.solid(c)), 120, self)
        self.power.clicked.connect(lambda: ctx.send(vm.power(ctx.status)))
        self.reset.clicked.connect(lambda: ctx.send({"cmd": "reset"}))
        self.bri.slider.valueChanged.connect(self._send_bri)
        self.colour["swatches"].picked.connect(lambda c: ctx.send(vm.solid(c)))
        self.colour["swatches"].remove.connect(lambda c: ctx.send(vm.remove_favourite(c)))
        self.colour["ring"].picked.connect(self._send_colour)
        self.colour["save"].clicked.connect(
            lambda: ctx.send(vm.save_favourite(self.colour["hex"].text())))
        for tid, tile in self.tiles.items():
            tile.clicked.connect(lambda _c=False, t=tid: self._pick_tile(t))
        ctx.status_changed.connect(self.show_status)

    def _pick_tile(self, tile_id):
        self.ctx.send(vm.tile_request(tile_id, self.ctx.status, self.remembered_effect))

    def show_status(self, s):
        if s.mode == "pattern" and s.args.get("name"):
            self.remembered_effect = (s.args["name"], int(s.args.get("speed", 50)))
        self.title.setText(s.name)
        self.state.setText(s.state_text())
        self.power.setText("On" if s.on else "Off")
        self.power.kind = "primary" if s.on else "raised"
        shadow(self.power, 22, s.accent, s.glow)
        self.power.update()
        self.bri.set_value(s.brightness)
        self.preview.set_state(s.on, s.brightness)
        self.colour["hex"].setText(s.accent.upper())
        self.colour["ring"].set_colour(s.accent, s.glow)
        self.colour["swatches"].set_swatches(vm.swatches(s))
        active = vm.active_tile(s)
        for tid, tile in self.tiles.items():
            tile.set_active(tid == active)
