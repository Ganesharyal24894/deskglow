"""The tray quick panel: power, brightness, favourites and quick modes."""
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, paint
from ..accent import accent
from ..throttle import Throttle
from ..vm import home as home_vm
from ..vm import tray as vm
from ..widgets.base import Button, Text, token
from ..widgets.colour import SwatchGrid
from ..widgets.controls import Slider, Toggle
from ..widgets.glow import TrayStrip


class TrayPanel(QWidget):
    open_app = Signal()
    quit_app = Signal()

    def __init__(self, ctx, popup=True, parent=None):
        super().__init__(parent)
        self.ctx, self.popup = ctx, popup
        if popup:
            self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(340, 520)
        col = QVBoxLayout(self)
        col.setContentsMargins(21, 21, 21, 21)
        col.setSpacing(18)
        head = QHBoxLayout()
        head.setSpacing(10)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.name = Text("Desk strip", fonts.display(16, 600))
        self.status = Text("", fonts.sans(12), "muted")
        names.addWidget(self.name)
        names.addWidget(self.status)
        head.addLayout(names, 1)
        self.power = Toggle()
        self.power.setAccessibleName("Power")
        head.addWidget(self.power)
        col.addLayout(head)
        self.strip = TrayStrip()
        col.addWidget(self.strip)
        bri = QHBoxLayout()
        bri.setSpacing(12)
        bri.addWidget(Text("Brightness", fonts.sans(13), "muted"))
        self.slider = Slider(0, 100, 80)
        bri.addWidget(self.slider, 1)
        self.value = Text("80%", fonts.sans(13, 600))
        self.value.setFixedWidth(40)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bri.addWidget(self.value)
        col.addLayout(bri)
        self.swatches = SwatchGrid(8, 44, inset_ring=False)
        col.addWidget(self.swatches)
        quick = QGridLayout()
        quick.setSpacing(8)
        self.quick = {}
        for i, (qid, label) in enumerate(vm.QUICK):
            b = Button(label, "raised", 44, 12, fonts.sans(13, 500))
            b.clicked.connect(lambda _c=False, q=qid: self._quick(q))
            quick.addWidget(b, i // 2, i % 2)
            self.quick[qid] = b
        col.addLayout(quick)
        col.addStretch(1)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 12, 0, 0)
        foot.setSpacing(8)
        self.open_button = Button("Open Deskglow", "plain", 36, 0, fonts.sans(13, 500), pad=0)
        foot.addWidget(self.open_button)
        foot.addStretch(1)
        self.quit_button = Button("Quit", "ghost", 36, 9, fonts.sans(13, 500), pad=12)
        foot.addWidget(self.quit_button)
        col.addLayout(foot)

        self._send_bri = Throttle(lambda v: ctx.send(home_vm.brightness(v)), 150, self)
        self.slider.valueChanged.connect(lambda v: self.value.setText(f"{v}%"))
        self.slider.valueChanged.connect(self._send_bri)
        self.power.toggled.connect(lambda _on: ctx.send(home_vm.power(ctx.status)))
        self.swatches.picked.connect(lambda c: ctx.send(home_vm.solid(c)))
        self.open_button.clicked.connect(self.open_app.emit)
        self.quit_button.clicked.connect(self.quit_app.emit)
        ctx.status_changed.connect(self.show_status)

    def _quick(self, tile_id):
        self.ctx.send(home_vm.tile_request(tile_id, self.ctx.status))

    def show_status(self, s):
        self.name.setText(s.name)
        self.status.setText(vm.status_line(s))
        self.power.blockSignals(True)
        self.power.setChecked(s.on)
        self.power.blockSignals(False)
        self.power.update()
        self.strip.on = s.on
        self.slider.set_quietly(s.brightness)
        if not self.slider.isSliderDown():
            self.value.setText(f"{s.brightness}%")
        self.swatches.set_swatches(home_vm.swatches(s))
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        if not self.popup:                      # embedded: square corners show the page
            paint.box(p, self.rect(), 0, token("bg"))
        paint.box(p, self.rect(), 18, token("card"), token("control_border"))
        if self.strip.on:
            r = QRectF(self.strip.bar_rect()).translated(self.strip.pos())
            level = self.ctx.status.brightness
            paint.glow(p, r, 5, accent(), 0.25 + 0.6 * level / 100.0, 28, 8)
        foot_y = self.open_button.geometry().top() - 12
        paint.box(p, QRectF(21, foot_y, self.width() - 42, 1), 0, token("card_border"))
        p.end()
