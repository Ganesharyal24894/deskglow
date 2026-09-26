"""First-run Setup: the daemon scans for strips; pick one (or type an address)."""
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .. import fonts, icons, paint, theme
from ..vm import setup as vm
from ..widgets.base import Button, Text, token
from ..widgets.candidate import CandidateRow
from ..widgets.glow import BrandMark
from .common import card


class Spinner(QWidget):
    """The arc icon; turns while a scan runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def spin(self, on):
        self._timer.start() if on else self._timer.stop()

    def _tick(self):
        self.angle = (self.angle + 12) % 360
        self.update()

    def paintEvent(self, _e):
        p = paint.begin(self)
        p.translate(9, 9)
        p.rotate(self.angle)
        icons.draw(p, -9, -9, 18, icons.SPINNER, token("accent_ink"), 2.2, join=False)
        p.end()


class SetupPage(QWidget):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.ctx, self.rows, self.scanning = ctx, [], False
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box = box = card(36, 22, 24)[0]
        lay = box.layout()
        box.setFixedWidth(540)
        outer.addWidget(box)
        lay.addWidget(BrandMark(18, (30, 9), 22))
        intro = QVBoxLayout()
        intro.setSpacing(8)
        intro.addWidget(Text("Let's find your strip", fonts.display(28, 600, -0.02)))
        para = Text("Plug it in and keep it within a few metres. Close the phone app first: "
                    "these strips accept one connection at a time.", fonts.sans(14), "muted", True)
        intro.addWidget(para)
        lay.addLayout(intro)
        status = QHBoxLayout()
        status.setSpacing(10)
        self.spinner = Spinner()
        status.addWidget(self.spinner)
        self.headline = Text("Scanning…", fonts.sans(13), "muted")
        status.addWidget(self.headline, 1)
        self.rescan = Button("Scan again", "outline", 36, 9, fonts.sans(13, 500), pad=12)
        status.addWidget(self.rescan)
        lay.addLayout(status)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        lay.addLayout(self.list)
        self.group = QButtonGroup(self)
        self.manual = QLineEdit()
        self.manual.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        self.manual.setFont(fonts.mono(14))
        self.manual.setFixedHeight(44)
        self.manual.hide()
        lay.addWidget(self.manual)
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.enter = Button("Enter address manually", "link", 46, 0, fonts.sans(14, 500), pad=4)
        bottom.addWidget(self.enter)
        bottom.addStretch(1)
        self.cancel = Button("Cancel", "plain", 46, 12, fonts.sans(14, 500), pad=12)
        self.cancel.hide()
        bottom.addWidget(self.cancel)
        self.use = Button("Use this strip", "primary", 46, 12, fonts.sans(14, 600), pad=22)
        bottom.addWidget(self.use)
        lay.addLayout(bottom)

        self.rescan.clicked.connect(self.scan)
        self.enter.clicked.connect(self._toggle_manual)
        self.manual.textChanged.connect(lambda _t: self._update_use())
        self.cancel.clicked.connect(lambda: ctx.navigate.emit("home"))
        self.use.clicked.connect(self._use)

    def paintEvent(self, _e):
        """The card's soft shadow (0 12px 40px, light theme only)."""
        p = paint.begin(self)
        r = QRectF(self.box.geometry()).translated(0, 12)
        paint.glow(p, r, 24, theme.SHADOW, theme.current().card_shadow, 40)
        p.end()

    def begin(self, back_allowed=False):
        self.cancel.setVisible(back_allowed)
        self.scan()

    def scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.spinner.spin(True)
        self.headline.setText(vm.headline(True, 0))
        self.rescan.setEnabled(False)
        self.ctx.send(vm.scan_request(), self._scanned, refresh=False)

    def _scanned(self, reply):
        self.scanning = False
        self.spinner.spin(False)
        self.rescan.setEnabled(True)
        found = reply.get("candidates") if reply.get("ok") else []
        self.show_rows(vm.rows(found or []), None if reply.get("ok") else reply.get("error"))

    def show_rows(self, rows, error=None):
        for w in self.rows:
            self.group.removeButton(w)
            self.list.removeWidget(w)
            w.deleteLater()
        self.rows = []
        for row in rows:
            w = CandidateRow(row)
            self.group.addButton(w)
            self.list.addWidget(w)
            self.rows.append(w)
            w.toggled.connect(lambda _on: self._update_use())
        if self.rows:
            self.rows[0].setChecked(True)
        self.headline.setText(vm.headline(False, len(rows), error))
        self._update_use()

    def _toggle_manual(self):
        self.manual.setVisible(not self.manual.isVisible())
        if self.manual.isVisible():
            self.manual.setFocus()
        self._update_use()

    def _choice(self):
        if self.manual.isVisible() and self.manual.text().strip():
            addr = vm.manual_address(self.manual.text())
            return vm.use_request(manual=addr) if addr else None
        chosen = next((w for w in self.rows if w.isChecked()), None)
        return vm.use_request(chosen.row) if chosen else None

    def _update_use(self):
        self.use.setEnabled(self._choice() is not None)

    def _use(self):
        req = self._choice()
        if req is None:
            return

        def done(reply):
            if reply.get("ok"):
                self.ctx.send({"cmd": "on"})
                self.ctx.navigate.emit("home")
        self.ctx.send(req, done)
