"""The accent colour: the strip's current colour, shared by every widget."""
from .theme import DEFAULT_ACCENT

_accent = [DEFAULT_ACCENT]


def accent():
    return _accent[0]


def set_accent(value):
    """Set the accent (#RRGGBB); True if it changed."""
    value = (value or DEFAULT_ACCENT).upper()
    changed = value != _accent[0]
    _accent[0] = value
    return changed
