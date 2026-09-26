"""Focus screen: ring from status, Start/Pause/Resume/Stop, steppers."""
import pytest
from gui_fakes import push
from PySide6.QtCore import Qt

from deskglow.view.gui.screens.focus import FocusPage

RUNNING = {"phase": "focus", "remaining": 1122.0, "total": 1500.0, "round": 2, "rounds": 4,
           "paused": False}


@pytest.fixture
def page(qtbot, ctx, client):
    p = FocusPage(ctx)
    qtbot.addWidget(p)
    p.resize(824, 720)
    p.show()
    push(ctx, client)
    client.requests.clear()
    return p


def click(qtbot, w):
    qtbot.mouseClick(w, Qt.MouseButton.LeftButton)


def test_idle_shows_the_configured_timer_and_start(page):
    assert page.clock.text() == "25:00" and page.round.text() == "Round 1 of 4"
    assert page.primary.text() == "Start" and not page.stop.isEnabled()
    assert [page.values[k].text() for k in ("work", "break", "rounds")] == ["25 min", "5 min", "4"]


def test_running_timer_matches_the_status(page, ctx, client):
    push(ctx, client, mode="pomodoro", focus=RUNNING)
    assert (page.phase.text(), page.clock.text(), page.round.text()) == (
        "FOCUS", "18:42", "Round 2 of 4")
    assert page.ring.fraction == pytest.approx(0.748)
    assert page.primary.text() == "Pause" and page.stop.isEnabled()


def test_start_sends_the_timer_settings(qtbot, page, client):
    click(qtbot, page.primary)
    assert client.sent() == [{"cmd": "set_mode", "mode": "pomodoro",
                              "args": {"work": 25, "break": 5, "rounds": 4}}]


def test_pause_and_resume(qtbot, page, ctx, client):
    push(ctx, client, mode="pomodoro", focus=RUNNING)
    click(qtbot, page.primary)
    assert client.sent() == [{"cmd": "focus_pause", "paused": True}]
    push(ctx, client, focus=dict(RUNNING, paused=True))
    assert page.primary.text() == "Resume"
    click(qtbot, page.primary)
    assert client.sent()[-1] == {"cmd": "focus_pause", "paused": False}


def test_stop_goes_back_to_the_last_colour(qtbot, page, ctx, client):
    push(ctx, client, mode="pomodoro", focus=RUNNING, last_solid="#00B8C7")
    click(qtbot, page.stop)
    assert client.sent() == [{"cmd": "set_mode", "mode": "solid", "args": {"rgb": [0, 184, 199]}}]


@pytest.mark.parametrize("key,button,expected", [
    ("work", 1, 30), ("work", 0, 20), ("break", 1, 6), ("break", 0, 4),
    ("rounds", 1, 5), ("rounds", 0, 3)])
def test_steppers_save_the_timer(qtbot, page, client, key, button, expected):
    click(qtbot, page.steps[key][button])
    req = client.sent()[-1]
    assert req["cmd"] == "config" and req["key"] == "focus_timer"
    assert req["value"][key] == expected
    assert page.values[key].text().startswith(str(expected))


def test_steppers_stop_at_their_limits(qtbot, page, ctx, client):
    push(ctx, client, focus_timer={"work": 25, "break": 5, "rounds": 12})
    click(qtbot, page.steps["rounds"][1])
    assert client.sent()[-1]["value"]["rounds"] == 12
