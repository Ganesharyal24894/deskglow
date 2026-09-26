"""Settings: the strip, app behaviour, theme, and about."""
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from ..throttle import Throttle
from ..vm import settings as vm
from .common import Page, h1
from .settings_parts import PROJECT_URL, about_card, app_card, strip_card

CONFIRM_MS = 3000


class SettingsPage(Page):
    def __init__(self, ctx, features=None, parent=None):
        super().__init__(20, parent)
        self.ctx, self.features = ctx, features
        self.body.addWidget(h1("Settings"))
        grid = QHBoxLayout()
        grid.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(20)
        strip, self.strip = strip_card()
        about, self.about = about_card()
        left.addWidget(strip)
        left.addWidget(about)
        left.addStretch(1)
        right = QVBoxLayout()
        right.setSpacing(20)
        app, self.toggles, self.themes = app_card()
        right.addWidget(app)
        right.addStretch(1)
        grid.addLayout(left, 1)
        grid.addLayout(right, 1)
        self.body.addLayout(grid, 1)

        st = self.strip
        st["name"].editingFinished.connect(self._rename)
        st["find"].clicked.connect(lambda: ctx.navigate.emit("setup"))
        st["forget"].clicked.connect(self._forget)
        self._confirm = QTimer(self)
        self._confirm.setSingleShot(True)
        self._confirm.timeout.connect(lambda: st["forget"].setText("Forget"))
        self._send_ceiling = Throttle(lambda v: ctx.send(vm.ceiling_request(v)), 200, self)
        st["ceiling"].valueChanged.connect(lambda v: st["ceil_value"].setText(f"{v}%"))
        st["ceiling"].valueChanged.connect(self._send_ceiling)
        for tid, row in self.toggles.items():
            row.switch.toggled.connect(lambda on, t=tid: self._flip(t, on))
        self.themes.picked.connect(self._theme)
        self.about["logs"].clicked.connect(self.open_logs)
        self.about["github"].clicked.connect(lambda: self.open_url(QUrl(PROJECT_URL)))
        ctx.status_changed.connect(self.show_status)
        ctx.local_changed.connect(lambda: self.show_status(ctx.status))

    def open_url(self, url):
        QDesktopServices.openUrl(url)

    def open_logs(self):
        path = self.ctx.log_path()
        if path:
            self.open_url(QUrl.fromLocalFile(path))

    def _rename(self):
        req = vm.rename_request(self.strip["name"].text(), self.ctx.status.name)
        if req is not None:
            self.ctx.send(req)

    def _forget(self):
        button = self.strip["forget"]
        if not self._confirm.isActive():
            button.setText("Confirm forget")
            button.updateGeometry()
            self._confirm.start(CONFIRM_MS)
            return
        self._confirm.stop()
        button.setText("Forget")
        self.ctx.send({"cmd": "forget"}, lambda r: r.get("ok") and self.ctx.navigate.emit("setup"))

    def _flip(self, toggle_id, on):
        if toggle_id == "login":
            if self.features is not None:
                self.features.set_login(on)
            return
        # the shortcut itself follows hotkey_on in the next status (Features)
        self.ctx.send(vm.toggle_request(toggle_id, on))

    def _theme(self, theme_id):
        if self.features is not None:
            self.features.apply_theme(theme_id)
        self.ctx.send(vm.theme_request(theme_id))

    def show_status(self, s):
        st = self.strip
        if not st["name"].hasFocus():
            st["name"].setText(s.name)
        address, model = vm.address_line(s)
        st["address"].setText(address)
        st["model"].setText(model)
        st["ceiling"].set_quietly(s.max_brightness)
        if not st["ceiling"].isSliderDown():
            st["ceil_value"].setText(f"{s.max_brightness}%")
        rows = vm.rows(s, self.ctx.login, self.ctx.hotkey, self.ctx.tray_available)
        for data in rows:
            self.toggles[data.id].show(data)
        self.themes.set_current(s.get("theme", "system"))
