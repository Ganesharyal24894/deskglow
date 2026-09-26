"""Painting helpers shared by the custom widgets: CSS-like boxes and glows."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPen,
                           QRadialGradient)


def qcolor(value, alpha=None):
    c = QColor(value)
    if alpha is not None:
        c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def begin(widget):
    p = QPainter(widget)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return p


def box(p, rect, radius, fill=None, border=None, width=1.0):
    """A CSS box: `fill` inside, a `width` border drawn inside the rect."""
    r = QRectF(rect)
    p.save()
    if fill is not None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcolor(fill)))
        p.drawRoundedRect(r, radius, radius)
    if border is not None and width > 0:
        half = width / 2.0
        inner = r.adjusted(half, half, -half, -half)
        pen = QPen(qcolor(border), width)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        rad = max(0.0, radius - half)
        p.drawRoundedRect(inner, rad, rad)
    p.restore()


def _profile(t, lo, hi, sigma):
    """Coverage of the interval [lo, hi] blurred by a Gaussian, at t."""
    k = sigma * math.sqrt(2.0)
    return 0.5 * (math.erf((t - lo) / k) - math.erf((t - hi) / k))


def _ramp(g, lo, hi, sigma, start, length, colour, alpha, samples=24):
    """Put the blurred-interval profile on a gradient spanning start..start+length."""
    for i in range(samples + 1):
        pos = i / samples
        g.setColorAt(pos, qcolor(colour, alpha * _profile(start + pos * length, lo, hi, sigma)))


def glow(p, rect, radius, color, alpha, blur, spread=0.0):
    """A CSS `box-shadow: 0 0 blur spread color` (at `alpha`) around `rect`.

    The shape (rect grown by `spread`) blurred by a Gaussian of sigma blur/2.
    Circles use a radial profile; other shapes the separable rectangle one,
    built from two erf gradients multiplied offscreen (no banding)."""
    if alpha <= 0 or blur <= 0:
        return
    sigma = blur / 2.0
    shape = QRectF(rect).adjusted(-spread, -spread, spread, spread)
    reach = 3.0 * sigma
    area = shape.adjusted(-reach, -reach, reach, reach)
    if abs(shape.width() - shape.height()) < 0.5 and radius >= min(rect.width(), rect.height()) / 2 - 0.5:
        g = QRadialGradient(shape.center(), area.width() / 2)
        r0 = shape.width() / 2
        _ramp(g, -r0, r0, sigma, 0.0, area.width() / 2, color, alpha)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(area)
        p.restore()
        return
    w, h = int(math.ceil(area.width())), int(math.ceil(area.height()))
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    ip = QPainter(img)
    ox, oy = area.left(), area.top()
    gx = QLinearGradient(0, 0, w, 0)
    _ramp(gx, shape.left() - ox, shape.right() - ox, sigma, 0.0, w, color, alpha, 48)
    ip.fillRect(0, 0, w, h, QBrush(gx))
    ip.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    gy = QLinearGradient(0, 0, 0, h)
    _ramp(gy, shape.top() - oy, shape.bottom() - oy, sigma, 0.0, h, "#000000", 1.0, 32)
    ip.fillRect(0, 0, w, h, QBrush(gy))
    ip.end()
    p.drawImage(QPointF(ox, oy), img)


def soft_shadow(p, rect, radius, color, alpha, dy=1.0, blur=2.0, layers=8):
    """A small CSS `box-shadow: 0 dy blur color` that follows rounded corners:
    the shape, offset by dy, box-blurred by stacking grown/shrunk copies."""
    if alpha <= 0:
        return
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(qcolor(color, alpha / layers)))
    base = QRectF(rect).translated(0, dy)
    for i in range(layers):
        g = blur * ((i + 0.5) / layers - 0.5)
        r = base.adjusted(-g, -g, g, g)
        p.drawRoundedRect(r, max(0.0, radius + g), max(0.0, radius + g))
    p.restore()


def text(p, rect, value, font, color, align=Qt.AlignmentFlag.AlignLeft
         | Qt.AlignmentFlag.AlignVCenter):
    p.save()
    p.setFont(font)
    p.setPen(qcolor(color))
    p.drawText(QRectF(rect), int(align), value)
    p.restore()
