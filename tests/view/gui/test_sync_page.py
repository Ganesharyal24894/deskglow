"""Sync screen: monitors from the daemon, target chips, styles, music card."""
import pytest
from gui_fakes import push
from PySide6.QtCore import Qt

from deskglow.view.gui.screens import sync as sync_screen
from deskglow.view.gui.screens.sync import SyncPage


@pytest.fixture
def page(qtbot, ctx, client):
    p = SyncPage(ctx)
    qtbot.addWidget(p)
    p.resize(824, 720)
    p.show()
    push(ctx, client)
    client.requests.clear()
    return p


def click_option(qtbot, seg, oid):
    qtbot.mouseClick(seg, Qt.MouseButton.LeftButton, pos=seg.rects()[oid].center().toPoint())


def test_monitors_come_from_the_daemon(page):
    assert [o for o, _l in page.screen["chips"].options] == ["focus", "both", "DP-1", "HDMI-1"]
    assert [b.name for b, _r in page.screen["diagram"].rects()] == ["DP-1", "HDMI-1"]


def test_qt_screens_are_the_fallback(qtbot, ctx, client, monkeypatch):
    client.replies["monitors"] = {"ok": False, "error": "no display"}
    monkeypatch.setattr(sync_screen, "qt_monitors",
                        lambda: {"Q-1": {"left": 0, "top": 0, "width": 800, "height": 600}})
    p = SyncPage(ctx)
    qtbot.addWidget(p)
    push(ctx, client)
    assert [o for o, _l in p.screen["chips"].options][-1] == "Q-1"


@pytest.mark.parametrize("target", ["both", "HDMI-1", "focus"])
def test_chips_pick_the_screen(qtbot, page, client, target):
    click_option(qtbot, page.screen["chips"], target)
    assert client.sent() == [{"cmd": "config", "key": "screen_monitor", "value": target}]
    assert page.screen["chips"].current == target


def test_clicking_a_monitor_in_the_diagram_picks_it(qtbot, page, client):
    diagram = page.screen["diagram"]
    _box, rect = diagram.rects()[1]
    qtbot.mouseClick(diagram, Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
    assert client.sent() == [{"cmd": "config", "key": "screen_monitor", "value": "HDMI-1"}]
    assert page.screen["diagram"].lit == {"HDMI-1"}


def test_style_segments_set_the_style_and_explain_it(qtbot, page, client):
    click_option(qtbot, page.screen["styles"], "edge")
    assert client.sent() == [{"cmd": "config", "key": "screen_style", "value": "edge"}]
    assert page.screen["desc"].text() == "Only the screen border, like an ambilight."


def test_start_and_stop_screen_sync(qtbot, page, ctx, client):
    qtbot.mouseClick(page.screen["start"], Qt.MouseButton.LeftButton)
    assert client.sent() == [{"cmd": "set_mode", "mode": "screen", "args": {"style": "vivid"}}]
    push(ctx, client, mode="screen", screen={"color": "#4A7BFF", "fps": 15.0})
    assert page.screen["start"].text() == "Stop screen sync"
    client.requests.clear()
    qtbot.mouseClick(page.screen["start"], Qt.MouseButton.LeftButton)
    assert client.sent()[0]["mode"] == "solid"


def test_live_readout_only_while_running(page, ctx, client):
    assert not page.screen["live"].isVisible()
    push(ctx, client, mode="screen", screen={"color": "#4A7BFF", "fps": 14.9})
    assert page.screen["live"].isVisible()
    assert page.screen["live_text"].text() == "#4A7BFF · 15 fps"


def test_music_source_and_start(qtbot, page, client):
    click_option(qtbot, page.music["sources"], "mic")
    assert client.sent() == []            # nothing running: just remembered
    qtbot.mouseClick(page.music["start"], Qt.MouseButton.LeftButton)
    assert client.sent() == [{"cmd": "set_mode", "mode": "audio", "args": {"source": "mic"}}]


def test_changing_source_while_music_runs_restarts_it(qtbot, page, ctx, client):
    push(ctx, client, mode="audio", args={"source": "system"}, audio_level=0.5)
    client.requests.clear()
    click_option(qtbot, page.music["sources"], "mic")
    assert client.sent() == [{"cmd": "set_mode", "mode": "audio", "args": {"source": "mic"}}]


def test_sensitivity_slider(page, client):
    page.music["sens"].setValue(90)
    assert client.sent() == [{"cmd": "config", "key": "audio_sensitivity", "value": 90}]


def test_meter_follows_the_audio_level_and_polls_faster(page, ctx, client):
    push(ctx, client, mode="audio", args={"source": "system"}, audio_level=0.8)
    assert page.meter.levels[-1] == 0.8
    assert page.music["meter"].heights[-1] == 0.8
    assert ctx.poller.interval() < 2000
    push(ctx, client, mode="solid", audio_level=None)
    assert page.meter.levels == [0.0] * 18
    assert ctx.poller.interval() == 2000
