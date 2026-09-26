"""vm.focus (ring, steppers, buttons) and vm.settings (toggle rows)."""
import pytest
from gui_fakes import status

from deskglow.view.gui.vm import focus, settings
from deskglow.view.gui.vm.settings import Capability
from deskglow.view.gui.vm.status import StatusView

RUNNING = {"phase": "focus", "remaining": 1122.0, "total": 1500.0, "round": 2, "rounds": 4,
           "paused": False}


def test_ring_while_running_matches_the_design_sample():
    r = focus.ring(StatusView(status(mode="pomodoro", focus=RUNNING)))
    assert (r.time_text, r.label, r.round_text) == ("18:42", "FOCUS", "Round 2 of 4")
    assert r.fraction == pytest.approx(0.748) and r.running and not r.paused
    assert r.colour == "#28A0C8"


def test_ring_when_idle_shows_the_configured_timer():
    r = focus.ring(StatusView(status(focus_timer={"work": 50, "break": 10, "rounds": 3})))
    assert (r.time_text, r.round_text, r.fraction, r.running) == ("50:00", "Round 1 of 3", 1.0,
                                                                 False)


def test_clock_rounds_up():
    assert focus.clock(0.2) == "00:01" and focus.clock(-3) == "00:00"


@pytest.mark.parametrize("key,direction,start,expected", [
    ("work", +1, 25, 30), ("work", -1, 25, 20), ("work", -1, 5, 4), ("work", -1, 1, 1),
    ("work", +1, 180, 180), ("break", +1, 5, 6), ("break", -1, 1, 1),
    ("rounds", +1, 12, 12), ("rounds", -1, 4, 3),
])
def test_steppers_move_and_clamp(key, direction, start, expected):
    timer = {"work": 25, "break": 5, "rounds": 4}
    timer[key] = start
    assert focus.step(timer, key, direction)[key] == expected


def test_value_text():
    assert focus.value_text("work", 25) == "25 min" and focus.value_text("rounds", 4) == "4"


def test_primary_button_start_pause_resume():
    assert focus.primary_button(StatusView(status()))[1]["mode"] == "pomodoro"
    running = StatusView(status(mode="pomodoro", focus=RUNNING))
    assert focus.primary_button(running) == ("Pause", {"cmd": "focus_pause", "paused": True})
    paused = StatusView(status(mode="pomodoro", focus=dict(RUNNING, paused=True)))
    assert focus.primary_button(paused) == ("Resume", {"cmd": "focus_pause", "paused": False})


def test_stop_returns_to_the_last_colour_only_while_running():
    assert focus.stop_request(StatusView(status(mode="pomodoro")))["mode"] == "solid"
    assert focus.stop_request(StatusView(status())) is None


def rows_for(**kw):
    s = StatusView(status(**kw.pop("st", {})))
    args = {"login": Capability(True, "", True), "hotkey": Capability(), "tray_available": True}
    args.update(kw)
    return {r.id: r for r in settings.rows(s, **args)}


def test_rows_reflect_status_and_capabilities():
    r = rows_for(st={"tray_on": True, "hotkey_on": True, "sunset_on": False})
    assert [r[k].checked for k in ("login", "tray", "hotkey", "sunset")] == [True, True, True, False]
    assert all(row.enabled for row in r.values())
    assert r["hotkey"].desc == "Ctrl+Alt+L toggles the strip anywhere"


def test_disabled_rows_explain_why():
    r = rows_for(st={"sunset_available": False, "sunset_on": True, "hotkey_on": True},
                 login=Capability(False, "Can't be changed on this system"),
                 hotkey=Capability(False, "Not available on this desktop"), tray_available=False)
    assert not any(row.enabled for row in r.values())
    assert r["sunset"].desc == settings.NO_SUNSET and not r["sunset"].checked
    assert r["hotkey"].desc == "Not available on this desktop" and not r["hotkey"].checked
    assert r["tray"].desc == settings.NO_TRAY and not r["tray"].checked
    assert r["login"].desc == "Can't be changed on this system"


def test_toggle_requests():
    assert settings.toggle_request("sunset", 1) == {"cmd": "config", "key": "sunset_on",
                                                    "value": True}
    assert settings.toggle_request("tray", False)["key"] == "tray_on"
    assert settings.toggle_request("hotkey", True)["key"] == "hotkey_on"
    assert settings.toggle_request("login", True) is None


def test_other_settings_requests():
    assert settings.theme_request("light") == {"cmd": "config", "key": "theme", "value": "light"}
    assert settings.ceiling_request(85.0)["value"] == 85
    assert settings.rename_request("  Shelf ", "Desk strip")["value"] == "Shelf"
    assert settings.rename_request("Desk strip", "Desk strip") is None
    assert settings.rename_request("   ", "Desk strip") is None
    assert settings.address_line(StatusView(status())) == ("A4:C1:38:5E:22:9B", "MELK-OA10")
    assert settings.address_line(StatusView({"ok": True})) == ("Not set", "")
