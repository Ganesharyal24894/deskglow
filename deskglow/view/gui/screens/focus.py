"""Focus: the Pomodoro ring timer, its controls, steppers and the legend."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import fonts, paint, theme
from ..vm import focus as vm
from ..vm.status import PHASE_COLOURS
from ..widgets.base import Button, Text, token
from ..widgets.glow import shadow
from ..widgets.meters import FocusRing
from .common import Page, card, h2, title_block


class CueDot(QWidget):
    """28x10 pill with its glow (drawn by a graphics effect, outside the pill)."""

    def __init__(self, colour, opacity, parent=None):
        super().__init__(parent)
        self.colour, self.opacity = colour, opacity
        self.setFixedSize(28, 10)
        self.apply_theme()

    def apply_theme(self):
        shadow(self, 14, token(self.colour), self.opacity)

    def paintEvent(self, _e):
        p = paint.begin(self)
        p.setOpacity(self.opacity)
        paint.box(p, self.rect(), 5, token(self.colour))
        p.end()


def stepper(label):
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(Text(label, fonts.sans(14)), 1)
    minus = Button("−", "raised", 44, 10, fonts.sans(18), pad=0, min_width=44)
    minus.setFixedWidth(44)
    minus.setAccessibleName(f"Decrease {label}")
    value = Text("", fonts.display(15, 600))
    value.setFixedWidth(64)
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    plus = Button("+", "raised", 44, 10, fonts.sans(18), pad=0, min_width=44)
    plus.setFixedWidth(44)
    plus.setAccessibleName(f"Increase {label}")
    for w in (minus, value, plus):
        row.addWidget(w)
    return row, minus, value, plus


def primary_fill(phase_colour):
    """The Start/Pause fill: the phase colour, or the palette's focus_primary
    for the focus phase; light palettes darken the others for white text."""
    if phase_colour == PHASE_COLOURS["focus"]:
        return token("focus_primary")
    scale = theme.current().ink_scale
    return phase_colour if scale >= 1 else theme.ink(phase_colour, 0.75)


class FocusPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__(20, parent)
        self.ctx = ctx
        self.timer = dict(ctx.status.focus_timer)
        titles, _t, _s = title_block(
            "Focus", "A Pomodoro timer you can see from the corner of your eye.")
        self.body.addLayout(titles)
        grid = QHBoxLayout()
        grid.setSpacing(20)
        timer_card, lay = card(0, 28)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ring = FocusRing()
        over = QVBoxLayout(self.ring)
        over.setSpacing(6)
        over.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase = Text("FOCUS", fonts.font(fonts.SANS, 13, 600, 0.08), "focus_label")
        self.clock = Text("25:00", fonts.display(64, 600, -0.03))
        self.round = Text("Round 1 of 4", fonts.sans(14), "muted")
        for w in (self.phase, self.clock, self.round):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            over.addWidget(w)
        lay.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.primary = Button("Start", "primary", 46, 12, fonts.sans(14, 600), pad=16, min_width=132)
        self.primary.text_override = "focus_on_accent"
        self.stop = Button("Stop", "raised", 46, 12, fonts.sans(14, 600), pad=16, min_width=132)
        buttons.addWidget(self.primary)
        buttons.addWidget(self.stop)
        lay.addLayout(buttons)
        grid.addWidget(timer_card, 1)

        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(20)
        settings, slay = card(20, 14)
        slay.addWidget(h2("Timer"))
        self.values, self.steps = {}, {}
        for key, label, _step, _unit in vm.STEPPERS:
            row, minus, value, plus = stepper(label)
            minus.clicked.connect(lambda _c=False, k=key: self._step(k, -1))
            plus.clicked.connect(lambda _c=False, k=key: self._step(k, +1))
            self.values[key], self.steps[key] = value, (minus, plus)
            slay.addLayout(row)
        side.addWidget(settings)
        cues, clay = card(20, 12)
        clay.addWidget(h2("What the light means"))
        for label, desc, colour, opacity in vm.CUES:
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(CueDot(colour, opacity))
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(Text(label, fonts.sans(14, 500)))
            text.addWidget(Text(desc, fonts.sans(12), "muted"))
            row.addLayout(text, 1)
            clay.addLayout(row)
        clay.addStretch(1)
        side.addWidget(cues, 1)
        host = QWidget()
        host.setFixedWidth(300)
        host.setLayout(side)
        grid.addWidget(host)
        self.body.addLayout(grid, 1)

        self.primary.clicked.connect(lambda: ctx.send(vm.primary_button(ctx.status)[1]))
        self.stop.clicked.connect(self._stop)
        ctx.status_changed.connect(self.show_status)
        self._show_timer()
        self.apply_theme()

    def _step(self, key, direction):
        self.timer = vm.step(self.timer, key, direction)
        self._show_timer()
        self.ctx.send(vm.save_timer(self.timer))

    def _stop(self):
        req = vm.stop_request(self.ctx.status)
        if req is not None:
            self.ctx.send(req)

    def _show_timer(self):
        for key, label in self.values.items():
            label.setText(vm.value_text(key, self.timer[key]))

    def show_status(self, s):
        self.timer = s.focus_timer
        self._show_timer()
        r = vm.ring(s)
        self.ring.set_ring(r.fraction, r.colour)
        self.phase.setText(r.label)
        self.clock.setText(r.time_text)
        self.round.setText(r.round_text)
        self.primary.setText(vm.primary_button(s)[0])
        self._phase_colour = r.colour
        self.apply_theme()
        self.stop.setEnabled(r.running)

    def apply_theme(self):
        fill = primary_fill(getattr(self, "_phase_colour", PHASE_COLOURS["focus"]))
        self.primary.fill_override = self.primary.border_override = fill
        self.primary.update()
