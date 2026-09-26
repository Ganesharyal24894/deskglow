"""The app stylesheet for the few stock widgets (sliders, inputs, menus).
Everything else is custom-painted from the palette."""


def stylesheet(p):
    """QSS for palette `p` (a theme.Palette)."""
    return f"""
QWidget#root, QStackedWidget, QWidget#page {{ background: {p.bg}; }}
QToolTip {{ color: {p.text}; background: {p.raised}; border: 1px solid {p.control_border}; }}
QSlider {{ background: transparent; }}
QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; background: {p.control_border}; }}
QSlider::sub-page:horizontal {{ height: 4px; border-radius: 2px; background: {p.text}; }}
QSlider::add-page:horizontal {{ height: 4px; border-radius: 2px; background: {p.control_border}; }}
QSlider::handle:horizontal {{ width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
    background: {p.text}; }}
QSlider::handle:horizontal:hover {{ background: {p.strong}; }}
QLineEdit {{ height: 44px; padding: 0 12px; background: {p.inset}; color: {p.text};
    border: 1px solid {p.control_border}; border-radius: 10px;
    selection-background-color: {p.seg_on}; }}
QLineEdit:focus {{ border: 1px solid {p.muted}; }}
QMenu {{ background: {p.card}; color: {p.text}; border: 1px solid {p.control_border};
    padding: 4px; border-radius: 8px; }}
QMenu::item {{ padding: 6px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {p.raised}; }}
QMenu::separator {{ height: 1px; background: {p.card_border}; margin: 4px 6px; }}
"""
