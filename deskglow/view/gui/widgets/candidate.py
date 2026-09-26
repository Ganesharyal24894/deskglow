"""One scanned strip in the Setup list (a radio row)."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QAbstractButton

from .. import fonts, paint
from .base import token

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class CandidateRow(QAbstractButton):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{row.name} {row.address}")

    def paintEvent(self, _e):
        p = paint.begin(self)
        r = QRectF(self.rect())
        on = self.isChecked()
        paint.box(p, r, 14, token("tile_active" if on else "tile"),
                  token("accent_ink" if on else "card_border"))
        mid = r.height() / 2
        radio = QRectF(17, mid - 9, 18, 18)
        if on:
            paint.box(p, radio, 9, None, token("accent_ink"), 5.0)
        else:
            paint.box(p, radio, 9, None, token("radio_off"), 2.0)
        name_f, addr_f, small = fonts.sans(14, 600), fonts.mono(12), fonts.sans(12)
        nh, ah = QFontMetricsF(name_f).height(), QFontMetricsF(addr_f).height()
        top = mid - (nh + 2 + ah) / 2
        x = 17 + 18 + 14
        paint.text(p, QRectF(x, top, 260, nh), self.row.name, name_f, token("text"), LEFT)
        if self.row.likely:
            bx = x + QFontMetricsF(name_f).horizontalAdvance(self.row.name) + 8
            badge_f = fonts.sans(11, 600)
            bw = QFontMetricsF(badge_f).horizontalAdvance("Most likely") + 16
            bh = QFontMetricsF(badge_f).height() + 4
            b = QRectF(bx, top + (nh - bh) / 2, bw, bh)
            paint.box(p, b, 10, token("badge_bg"))
            paint.text(p, b, "Most likely", badge_f, token("accent_ink"), Qt.AlignmentFlag.AlignCenter)
        paint.text(p, QRectF(x, top + nh + 2, 260, ah), self.row.address, addr_f,
                   token("muted"), LEFT)
        right = r.width() - 17
        paint.text(p, QRectF(right - 50, 0, 50, r.height()), self.row.signal_text, small,
                   token("muted"), RIGHT)
        bars_x = right - 50 - 14 - 25
        for n in range(1, 5):
            h = n * 4 + 2
            colour = token("text" if n <= self.row.level else "bar_off")
            paint.box(p, QRectF(bars_x + (n - 1) * 7, mid + 9 - h, 4, h), 2, colour)
        p.end()
