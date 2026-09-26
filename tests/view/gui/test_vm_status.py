"""vm.status: reading a status reply the way the screens need it."""
import pytest
from gui_fakes import status

from deskglow.view.gui.vm.status import StatusView, colour_name, glow_alpha


def test_unreachable_daemon_reads_as_off_and_says_so():
    s = StatusView({"ok": False, "error": "no socket"})
    assert s.reachable is False and s.on is False
    assert s.state_text() == "Can't reach the Deskglow service"
    assert s.connection() == ("Service not running", "idle")
    stale = StatusView({"ok": False, "mode": "solid"})
    assert stale.on is False, "an error reply never means the strip is on"


def test_solid_state_text_names_the_swatch_and_level():
    s = StatusView(status())
    assert s.on and s.state_text() == "Warm white · 80%"
    assert StatusView(status(color="#123456")).state_text() == "Custom colour · 80%"


@pytest.mark.parametrize("mode,label", [("screen", "Screen sync"), ("audio", "Music"),
                                        ("pattern", "Effects"), ("pomodoro", "Focus")])
def test_state_text_names_the_mode(mode, label):
    assert StatusView(status(mode=mode, brightness=40)).state_text() == f"{label} · 40%"


def test_off_is_just_off():
    assert StatusView(status(mode="off")).state_text() == "Off"


def test_accent_is_the_solid_colour_else_the_last_solid():
    assert StatusView(status(color="#FF3B30")).accent == "#FF3B30"
    assert StatusView(status(mode="calm", color="#5A8CAA", last_solid="#00B8C7")).accent == "#00B8C7"
    assert StatusView(status(mode="off", color=None, last_solid=None)).accent == "#FFB46E"


def test_focus_accent_follows_the_timer_phase():
    s = StatusView(status(mode="pomodoro", focus={"phase": "break"}))
    assert s.accent == "#46B45A"
    assert StatusView(status(mode="pomodoro", focus=None)).accent == "#28A0C8"


@pytest.mark.parametrize("over,expected", [
    ({"configured": False}, ("No strip set up", "idle")),
    ({"connected": True}, ("Connected", "ok")),
    ({"connected": False, "mode": "off"}, ("Standby", "idle")),
    ({"connected": False, "mode": "calm"}, ("Connecting…", "warn")),
])
def test_connection_line(over, expected):
    assert StatusView(status(**over)).connection() == expected


def test_rssi_only_when_known_and_connected():
    assert StatusView(status(rssi=-58)).rssi_text() == "-58 dBm"
    assert StatusView(status(rssi=None)).rssi_text() == ""
    assert StatusView(status(rssi=-58, connected=False)).rssi_text() == ""


def test_glow_matches_the_design_formula():
    assert glow_alpha(True, 80) == pytest.approx(0.73)
    assert glow_alpha(False, 80) == 0.0
    assert StatusView(status(brightness=100)).glow == pytest.approx(0.85)


def test_defaults_fill_missing_fields():
    s = StatusView({"ok": True})
    assert s.favourites[0] == "#FFB46E" and len(s.favourites) == 8
    assert s.focus_timer == {"work": 25, "break": 5, "rounds": 4}
    assert s.name == "Desk strip" and s.brightness == 100 and s.args == {}
    assert s.flag("tray_on") is True and s.flag("sunset_on") is False


def test_colour_names():
    assert colour_name("#ffb46e") == "Warm white"
    assert colour_name(None) == "Custom colour"
