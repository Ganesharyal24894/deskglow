"""Poll the daemon's status on a timer, never with two requests in flight."""
from PySide6.QtCore import QObject, QTimer, Signal

INTERVAL_MS = 2000
FAST_MS = 500          # while a live reading (level meter) is on screen


class StatusPoller(QObject):
    updated = Signal(dict)

    def __init__(self, bridge, interval_ms=INTERVAL_MS, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.in_flight = False
        self._again = False
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll)

    def start(self):
        self._timer.start()
        self.poll()

    def stop(self):
        self._timer.stop()

    def set_fast(self, fast):
        self._timer.setInterval(FAST_MS if fast else INTERVAL_MS)

    def interval(self):
        return self._timer.interval()

    def poll(self):
        """Ask for status now. A tick that lands while one is in flight is
        skipped; an explicit refresh is remembered and sent right after."""
        if self.in_flight:
            return
        self.in_flight = True
        self.bridge.request({"cmd": "status"}, self._on_reply, timeout=5.0)

    def refresh(self):
        """Status soon, e.g. right after a command changed something."""
        if self.in_flight:
            self._again = True
        else:
            self.poll()

    def _on_reply(self, reply):
        self.in_flight = False
        self.updated.emit(reply if isinstance(reply, dict) else {"ok": False})
        if self._again:
            self._again = False
            self.poll()
