"""The main window: first-run Setup, or the sidebar plus one page at a time."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QWidget

from .screens.sidebar import Sidebar

WIDTH, HEIGHT = 1040, 720


class Shell(QWidget):
    """Sidebar + the page stack."""

    def __init__(self, ctx, pages, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.sidebar = Sidebar()
        lay.addWidget(self.sidebar)
        self.stack = QStackedWidget()
        self.pages = dict(pages)
        for page in self.pages.values():
            self.stack.addWidget(page)
        lay.addWidget(self.stack, 1)
        self.sidebar.picked.connect(self.show_page)
        ctx.status_changed.connect(self.sidebar.card.show_status)
        self.show_page("home")

    def show_page(self, page_id):
        self.stack.setCurrentWidget(self.pages[page_id])
        self.sidebar.set_active(page_id)
        self.current = page_id


class MainWindow(QWidget):
    """Setup until a strip is configured, then the app. Closing hides to the
    tray when "Keep running in the tray" is on and a tray exists."""

    page_changed = Signal(str)

    def __init__(self, ctx, pages, setup, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("root")
        self.setWindowTitle("Deskglow")
        self.resize(WIDTH, HEIGHT)
        self.setMinimumSize(WIDTH, HEIGHT)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.top = QStackedWidget()
        lay.addWidget(self.top)
        self.shell = Shell(ctx, pages)
        self.setup = setup
        self.top.addWidget(self.shell)
        self.top.addWidget(setup)
        self.quitting = False
        self._was_configured = None
        ctx.navigate.connect(self.go)
        ctx.status_changed.connect(self._follow_status)

    def go(self, page_id):
        if page_id == "setup":
            self.setup.begin(back_allowed=self.ctx.status.configured)
            self.top.setCurrentWidget(self.setup)
        else:
            self.top.setCurrentWidget(self.shell)
            self.shell.show_page(page_id)
        self.page_changed.emit(self.current_page())

    def current_page(self):
        return "setup" if self.top.currentWidget() is self.setup else self.shell.current

    def _follow_status(self, s):
        """Go to Setup on the first status without a strip, or when the strip is
        forgotten. A stale reply that raced a successful setup must not bounce
        the user back, hence only on a change (a down daemon is neither)."""
        if not s.reachable:
            return
        was, self._was_configured = self._was_configured, s.configured
        if not s.configured and was is not False and self.current_page() != "setup":
            self.go("setup")

    def close_to_tray(self):
        s = self.ctx.status
        return self.ctx.tray_available and s.flag("tray_on") and not self.quitting

    def closeEvent(self, event):
        if self.close_to_tray():
            event.ignore()
            self.hide()
        else:
            event.accept()
