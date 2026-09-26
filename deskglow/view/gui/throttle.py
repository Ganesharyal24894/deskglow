"""Latest-wins rate limiting for drags (sliders, the hue ring)."""
from PySide6.QtCore import QObject, QTimer

_UNSET = object()


class Throttle(QObject):
    """Call fn(value) at once, then at most every `ms` with the newest value."""

    def __init__(self, fn, ms=150, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._pending = _UNSET
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(ms)
        self._timer.timeout.connect(self._flush)

    def __call__(self, value):
        if self._timer.isActive():
            self._pending = value
            return
        self.fn(value)
        self._timer.start()

    def _flush(self):
        if self._pending is not _UNSET:
            value, self._pending = self._pending, _UNSET
            self.fn(value)
            self._timer.start()
