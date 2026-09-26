"""vm.setup (scan rows), vm.hue (ring geometry), vm.tray, and the theme registry."""
import pytest
from gui_fakes import status

from deskglow.view.gui import theme
from deskglow.view.gui.vm import hue, setup, tray
from deskglow.view.gui.vm.status import StatusView

CANDS = [{"address": "A4:C1:38:5E:22:9B", "name": "MELK-OA10", "rssi": -55, "certain": True},
         {"address": "BE:32:57:A0:13:6C", "name": "ELK-BLEDOM", "rssi": -76, "certain": False},
         {"address": "C4:18:E9:02:7F:21", "name": "", "rssi": None, "certain": False}]


@pytest.mark.parametrize("rssi,expected", [(-40, (4, "Strong")), (-65, (3, "Good")),
                                           (-76, (2, "Fair")), (-95, (1, "Weak")),
                                           (None, (0, "Unknown"))])
def test_signal_bars(rssi, expected):
    assert setup.signal(rssi) == expected


def test_rows_mark_the_first_certain_one_most_likely():
    rows = setup.rows(CANDS)
    assert [r.likely for r in rows] == [True, False, False]
    assert rows[2].name == "(unknown)" and rows[1].signal_text == "Fair"
    assert setup.rows([dict(CANDS[1])])[0].likely          # the only one found
    assert not setup.rows([CANDS[1], CANDS[0]])[0].likely  # an uncertain first


def test_headline():
    assert setup.headline(True, 0) == "Scanning…"
    assert setup.headline(False, 3) == "Found 3 LED controllers"
    assert setup.headline(False, 1) == "Found 1 LED controller"
    assert setup.headline(False, 0) == "No LED controllers found"
    assert setup.headline(False, 0, "adapter off") == "Scan failed: adapter off"


def test_use_requests():
    row = setup.rows(CANDS)[0]
    assert setup.use_request(row) == {"cmd": "set_address", "address": "A4:C1:38:5E:22:9B",
                                      "name": "MELK-OA10", "rssi": -55}
    assert setup.use_request(manual="A4:C1:38:5E:22:9B") == {
        "cmd": "set_address", "address": "A4:C1:38:5E:22:9B"}
    assert setup.manual_address("a4:c1:38:5e:22:9b") == "A4:C1:38:5E:22:9B"
    assert setup.manual_address("nope") is None
    assert setup.scan_request()["cmd"] == "scan"


def test_hue_ring_angles_and_colours():
    assert hue.colour_at(0) == "#FF3B30"
    assert hue.colour_at(360.0 / 7) == "#FFCC00"
    assert hue.colour_at(360.0 / 14) == "#FF8418"      # halfway red -> yellow
    assert hue.angle_of(0, -10) == 0.0 and hue.angle_of(10, 0) == 90.0
    assert hue.angle_of(0, 10) == 180.0
    for c in ("#FFCC00", "#34C759", "#007AFF"):
        assert hue.colour_at(hue.angle_for(c)) == c
    assert 20 < hue.angle_for("#FFB46E") < 40


def test_hue_band_and_marker():
    assert hue.on_band(0, -53) and not hue.on_band(0, -20) and not hue.on_band(0, -70)
    dx, dy = hue.marker_centre(90)
    assert dx == pytest.approx(53) and dy == pytest.approx(0, abs=1e-9)


def test_tray_status_line():
    assert tray.status_line(StatusView(status())) == "Solid colour · connected"
    assert tray.status_line(StatusView(status(mode="off", connected=False))) == "Off · standby"
    assert tray.status_line(StatusView(status(mode="calm"))) == "Calm · connected"
    assert tray.status_line(StatusView({"ok": False})) == "Service not running"
    assert tray.menu_power_label(StatusView(status())) == "Turn off"


def test_theme_registry_falls_back_to_dark_until_a_light_palette_exists(monkeypatch):
    assert theme.resolve("dark") is theme.DARK
    assert theme.resolve("light") is theme.DARK
    assert theme.resolve("system", system_dark=False) is theme.DARK
    light = theme.Palette(**{**theme.DARK.__dict__, "name": "light", "bg": "#FFFFFF"})
    monkeypatch.setitem(theme.PALETTES, "light", light)
    assert theme.resolve("light") is light
    assert theme.resolve("system", system_dark=False) is light
    assert theme.resolve("system", system_dark=True) is theme.DARK


def test_set_current_reports_changes():
    assert theme.set_current(theme.DARK) is False
    other = theme.Palette(**{**theme.DARK.__dict__, "name": "x"})
    assert theme.set_current(other) is True and theme.current() is other


def test_accent_ink_is_the_accent_scaled_by_the_palette(monkeypatch):
    from deskglow.view.gui import accent
    from deskglow.view.gui.widgets.base import token
    accent.set_accent("#FFB46E")
    assert token("accent") == token("accent_ink") == "#FFB46E"      # dark: unchanged
    theme.set_current(theme.Palette(**{**theme.DARK.__dict__, "ink_scale": 0.55}))
    assert token("accent_ink") == "#8C633D" and token("accent") == "#FFB46E"
