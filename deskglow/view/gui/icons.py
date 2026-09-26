"""The design's line icons (24x24 viewBox SVG markup), drawn with QSvgRenderer."""
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtSvg import QSvgRenderer


def _p(*ds):
    return "".join(f'<path d="{d}"/>' for d in ds)


HOME = _p("M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z")
EFFECTS = _p("M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5"
             "M15.5 8.5 18 6")
SYNC = _p("M5 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM8 20h8M12 16v4")
FOCUS = _p("M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM12 9v4l2.5 2M9 2h6")
SETTINGS = _p("M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4")
BLUETOOTH = _p("m7 7 10 10-5 5V2l5 5L7 17")
RESET = _p("M3 12a9 9 0 1 0 3-6.7L3 8", "M3 3v5h5")
POWER = _p("M12 3v9", "M6.3 6.3a8 8 0 1 0 11.4 0")
SUN = ('<circle cx="12" cy="12" r="4"/>'
       + _p("M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4"
            "M17.7 6.3l1.4-1.4"))
MOON = _p("M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z")
PLUS = _p("M12 5v14M5 12h14")
MUSIC = _p("M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z")
CALM = _p("M2 12c2.5-4 5-4 7.5 0s5 4 7.5 0 3.5-2.7 5-2")
CIRCADIAN = _p("M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M2 12h2M20 12h2"
               "M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4")
SPINNER = _p("M21 12a9 9 0 1 1-6.2-8.6")

_cache = {}


def svg(markup, color, stroke=1.8, join=True):
    """The full SVG document for an icon in `color`."""
    j = ' stroke-linejoin="round"' if join else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round"{j}>'
            f"{markup}</svg>")


def renderer(markup, color, stroke=1.8, join=True):
    key = (markup, color, stroke, join)
    r = _cache.get(key)
    if r is None:
        r = _cache[key] = QSvgRenderer(QByteArray(svg(markup, color, stroke, join).encode()))
    return r


def draw(painter, x, y, size, markup, color, stroke=1.8, join=True):
    """Paint an icon into the size x size square at (x, y)."""
    renderer(markup, color, stroke, join).render(painter, QRectF(x, y, size, size))
