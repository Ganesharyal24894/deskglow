"""Settings cards: Strip, App (toggles + theme), About."""
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .... import __version__
from .. import fonts
from ..vm import settings as vm
from ..widgets.base import Button, Text
from ..widgets.controls import Segmented, Slider, Toggle
from .common import card, h2, small

PROJECT_URL = "https://github.com/Ganesharyal24894/deskglow"


def strip_card():
    c, lay = card(20, 14)
    lay.addWidget(h2("Strip"))
    name_col = QVBoxLayout()
    name_col.setSpacing(6)
    name_col.addWidget(small("Name"))
    name = QLineEdit("Desk strip")
    name.setFont(fonts.sans(14))
    name.setFixedHeight(44)
    name.setMaxLength(40)
    name.setAccessibleName("Name")
    name_col.addWidget(name)
    lay.addLayout(name_col)
    addr_row = QHBoxLayout()
    addr_row.setSpacing(10)
    addr_row.addWidget(small("Address"))
    address = Text("", fonts.mono(13))
    addr_row.addWidget(address)
    addr_row.addStretch(1)
    model = small("")
    addr_row.addWidget(model)
    lay.addLayout(addr_row)
    buttons = QHBoxLayout()
    buttons.setSpacing(10)
    find = Button("Find another strip", "raised", 44, 10, fonts.sans(14, 500))
    forget = Button("Forget", "danger", 44, 10, fonts.sans(14, 500), pad=16)
    buttons.addWidget(find, 1)
    buttons.addWidget(forget)
    lay.addLayout(buttons)
    ceil_col = QVBoxLayout()
    ceil_col.setSpacing(6)
    head = QHBoxLayout()
    head.addWidget(small("Maximum brightness"), 1)
    ceil_value = small("100%", "text")
    head.addWidget(ceil_value)
    ceil_col.addLayout(head)
    ceiling = Slider(0, 100, 100)
    ceil_col.addWidget(ceiling)
    ceil_col.addWidget(Text("A cap for every mode. Lower it if your power supply is small.",
                            fonts.sans(12), "muted", wrap=True))
    lay.addLayout(ceil_col)
    return c, {"name": name, "address": address, "model": model, "find": find,
               "forget": forget, "ceiling": ceiling, "ceil_value": ceil_value}


def about_card():
    c, lay = card(20, 12, horizontal=True)
    col = QVBoxLayout()
    col.setSpacing(0)
    col.addWidget(Text(f"Deskglow {__version__}", fonts.sans(14, 600)))
    col.addWidget(Text("MIT licensed · open source", fonts.sans(12), "muted"))
    lay.addLayout(col, 1)
    logs = Button("Open logs", "raised", 40, 10, fonts.sans(13, 500), pad=14)
    github = Button("GitHub", "raised", 40, 10, fonts.sans(13, 500), pad=14)
    lay.addWidget(logs)
    lay.addWidget(github)
    return c, {"logs": logs, "github": github}


class ToggleRow:
    def __init__(self, layout, label):
        self.host = QWidget()
        self.host.setMinimumHeight(52)
        row = QHBoxLayout(self.host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.label = Text(label, fonts.sans(14))
        self.desc = Text("", fonts.sans(12), "muted", wrap=True)
        col.addStretch(1)
        col.addWidget(self.label)
        col.addWidget(self.desc)
        col.addStretch(1)
        row.addLayout(col, 1)
        self.switch = Toggle()
        self.switch.setAccessibleName(label)
        row.addWidget(self.switch)
        layout.addWidget(self.host)

    def show(self, data):
        self.desc.setText(data.desc)
        self.switch.blockSignals(True)
        self.switch.setChecked(data.checked)
        self.switch.blockSignals(False)
        self.switch.setEnabled(data.enabled)
        self.label.set_colour("text" if data.enabled else "muted")


def app_card():
    c, lay = card(20, 4)
    title = h2("App")
    title.setContentsMargins(0, 0, 0, 8)
    lay.addWidget(title)
    rows = {}
    for tid, label, _desc in vm.TOGGLES:
        rows[tid] = ToggleRow(lay, label)
    theme_host = QWidget()
    theme_host.setMinimumHeight(52)
    theme_row = QHBoxLayout(theme_host)
    theme_row.setContentsMargins(0, 0, 0, 0)
    theme_row.setSpacing(12)
    theme_row.addWidget(Text("Theme", fonts.sans(14)), 1)
    themes = Segmented(vm.THEMES, "system", height=34, radius=8, well_radius=10, pad=12)
    theme_row.addWidget(themes)
    lay.addWidget(theme_host)
    return c, rows, themes
