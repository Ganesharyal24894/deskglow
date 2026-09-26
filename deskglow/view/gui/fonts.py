"""The bundled typefaces (OFL, see assets/fonts/) and a QFont factory.

Sora and IBM Plex Sans ship as variable fonts; Qt only applies their weight
through the `wght` axis (QFont.setWeight alone would synthesise a fake bold),
so `font()` sets the axis. IBM Plex Mono ships as static Regular/Medium.
"""
from PySide6.QtCore import QDir, QFileInfo
from PySide6.QtGui import QFont, QFontDatabase

DISPLAY = "Sora"            # headings and numbers
SANS = "IBM Plex Sans"      # body text
MONO = "IBM Plex Mono"      # hex values and addresses

_loaded = []


def assets_dir():
    return QFileInfo(__file__).absolutePath() + "/assets/fonts"


def load():
    """Register the bundled fonts once; returns the families that loaded."""
    if _loaded:
        return list(_loaded)
    folder = QDir(assets_dir())
    for name in sorted(folder.entryList(["*.ttf"])):
        fid = QFontDatabase.addApplicationFont(folder.filePath(name))
        if fid >= 0:
            _loaded.extend(QFontDatabase.applicationFontFamilies(fid))
    return list(_loaded)


def font(family=SANS, px=14, weight=400, spacing_em=0.0):
    """A QFont at `px` pixels and CSS `weight`, with CSS letter-spacing in em."""
    f = QFont(family)
    f.setPixelSize(px)
    if family == MONO:
        f.setWeight(QFont.Weight.Medium if weight >= 500 else QFont.Weight.Normal)
    else:
        f.setVariableAxis(QFont.Tag("wght"), float(weight))
    if spacing_em:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing_em * px)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def sans(px=14, weight=400):
    return font(SANS, px, weight)


def display(px=15, weight=600, spacing_em=0.0):
    return font(DISPLAY, px, weight, spacing_em)


def mono(px=13, weight=400):
    return font(MONO, px, weight)
