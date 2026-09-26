"""Sync: follow the screen (with a diagram of the real monitors) or music."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout

from ..throttle import Throttle
from ..vm import sync as vm
from .common import Page, title_block
from .sync_parts import music_card, screen_card


def qt_monitors():
    """Fallback when the daemon can't list screens: Qt's view of them."""
    out = {}
    for s in QGuiApplication.screens():
        g = s.geometry()
        out[s.name() or f"Screen {len(out) + 1}"] = {
            "left": g.x(), "top": g.y(),
            "width": round(g.width() * s.devicePixelRatio()),
            "height": round(g.height() * s.devicePixelRatio())}
    return out


class SyncPage(Page):
    def __init__(self, ctx, parent=None):
        super().__init__(20, parent)
        self.ctx = ctx
        self.monitors, self._asked = {}, False
        self.source = "system"
        self.meter = vm.Meter()
        titles, _t, _s = title_block("Sync", "Let the strip follow your screen or your music.")
        self.body.addLayout(titles)
        grid = QHBoxLayout()
        grid.setSpacing(20)
        left, self.screen = screen_card()
        right, self.music = music_card()
        grid.addWidget(left, 125)
        grid.addWidget(right, 100)
        self.body.addLayout(grid, 1)

        s, m = self.screen, self.music
        s["chips"].picked.connect(self._target)
        s["diagram"].picked.connect(self._target)
        s["styles"].picked.connect(self._style)
        s["start"].clicked.connect(
            lambda: ctx.send(vm.screen_button(ctx.status, s["styles"].current)[1]))
        m["sources"].picked.connect(self._source)
        self._send_sens = Throttle(lambda v: ctx.send(vm.set_sensitivity(v)), 200, self)
        m["sens"].valueChanged.connect(self._send_sens)
        m["start"].clicked.connect(lambda: ctx.send(vm.music_button(ctx.status, self.source)[1]))
        ctx.status_changed.connect(self.show_status)
        self.set_monitors({})

    # ---- monitors ----------------------------------------------------------

    def load_monitors(self):
        self._asked = True
        self.ctx.send({"cmd": "monitors"}, self._got_monitors, refresh=False)

    def _got_monitors(self, reply):
        mons = reply.get("monitors") if reply.get("ok") else None
        self.set_monitors(mons or qt_monitors())

    def set_monitors(self, monitors):
        self.monitors = dict(monitors)
        chips = self.screen["chips"]
        chips.set_options(vm.targets(self.monitors))
        self._paint_diagram(chips.current)

    def _paint_diagram(self, target):
        live = vm.readout(self.ctx.status)
        glow = live[0] if live else self.ctx.status.accent
        lit = [b.name for b in vm.boxes(self.monitors) if vm.lit(target, b.name, self.monitors)]
        self.screen["diagram"].set_state(vm.boxes(self.monitors), lit, glow)

    # ---- actions -------------------------------------------------------------

    def _target(self, target):
        self.screen["chips"].set_current(target)
        self._paint_diagram(target)
        self.ctx.send(vm.set_target(target))

    def _style(self, style):
        self.screen["desc"].setText(vm.STYLE_DESCS[style])
        self.ctx.send(vm.set_style(style))

    def _source(self, source):
        self.source = source
        req = vm.source_change(self.ctx.status, source)
        if req is not None:
            self.ctx.send(req)

    def meter_demo(self, levels_pct):
        """Show fixed bar heights (screenshots)."""
        self.meter.levels = [v / 100.0 for v in levels_pct]
        self.music["meter"].set_heights(self.meter.heights())
        self._demo = True

    # ---- status ----------------------------------------------------------------

    def show_status(self, st):
        if st.reachable and not self._asked:
            self.load_monitors()
        s, m = self.screen, self.music
        target = st.get("screen_monitor", "focus")
        s["chips"].set_current(target)
        s["styles"].set_current(st.get("screen_style", "vivid"))
        s["desc"].setText(vm.STYLE_DESCS.get(s["styles"].current, ""))
        live = vm.readout(st)
        s["live"].setVisible(live is not None)
        if live:
            s["swatch"].set_colour(live[0])
            s["live_text"].setText(f"{live[0]} · {live[1]}")
        s["start"].setText(vm.screen_button(st, s["styles"].current)[0])
        self._paint_diagram(target)
        if st.mode == "audio":
            self.source = st.args.get("source", self.source)
            self.meter.push(st.get("audio_level", 0.0))
        elif not getattr(self, "_demo", False):
            self.meter.reset()
        m["sources"].set_current(self.source)
        m["meter"].set_heights(self.meter.heights())
        m["sens"].set_quietly(st.get("audio_sensitivity", 60))
        m["start"].setText(vm.music_button(st, self.source)[0])
        self.ctx.poller.set_fast(self.isVisible() and st.mode == "audio")

    def hideEvent(self, e):
        self.ctx.poller.set_fast(False)
        super().hideEvent(e)
