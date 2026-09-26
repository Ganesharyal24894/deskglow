"""Effects screen: filter, tiles start effects, the speed slider, status sync."""
import pytest
from gui_fakes import push
from PySide6.QtCore import Qt

from deskglow.view.gui.screens.effects import EffectsPage


@pytest.fixture
def page(qtbot, ctx, client):
    p = EffectsPage(ctx)
    qtbot.addWidget(p)
    p.resize(824, 720)
    p.show()
    push(ctx, client)
    client.requests.clear()
    return p


def visible(page):
    return [eid for eid, t in page.tiles.items() if t.isVisible()]


def click_filter(qtbot, page, fid):
    r = page.filters.rects()[fid]
    qtbot.mouseClick(page.filters, Qt.MouseButton.LeftButton, pos=r.center().toPoint())


@pytest.mark.parametrize("fid,count", [("fade", 12), ("jump", 2), ("blink", 8), ("all", 22)])
def test_filter_shows_only_that_kind(qtbot, page, fid, count):
    click_filter(qtbot, page, fid)
    assert len(visible(page)) == count
    assert page.filters.current == fid
    if fid != "all":
        assert all(eid.startswith(fid) for eid in visible(page))


def test_filter_does_not_talk_to_the_daemon(qtbot, page, client):
    click_filter(qtbot, page, "blink")
    assert client.sent() == []


def test_clicking_a_tile_plays_it_at_the_current_speed(qtbot, page, client):
    page.speed.setValue(70)
    client.requests.clear()
    qtbot.mouseClick(page.tiles["blink-red"], Qt.MouseButton.LeftButton)
    assert client.sent() == [{"cmd": "set_mode", "mode": "pattern",
                              "args": {"name": "blink-red", "speed": 70}}]
    assert page.tiles["blink-red"].active and page.now.text() == "Blink · Red"


def test_speed_changes_restart_a_playing_effect(page, ctx, client):
    push(ctx, client, mode="pattern", args={"name": "fade-blue", "speed": 50}, color=None)
    client.requests.clear()
    page.speed.setValue(80)
    assert client.sent() == [{"cmd": "set_mode", "mode": "pattern",
                              "args": {"name": "fade-blue", "speed": 80}}]
    assert page.speed_value.text() == "80"


def test_speed_alone_does_nothing_when_no_effect_plays(page, client):
    page.speed.setValue(10)
    assert client.sent() == []


def test_status_selects_the_playing_effect_and_its_speed(page, ctx, client):
    push(ctx, client, mode="pattern", args={"name": "jump-colors", "speed": 33}, color=None)
    assert [e for e, t in page.tiles.items() if t.active] == ["jump-colors"]
    assert page.speed.value() == 33 and page.speed_value.text() == "33"
    assert page.playing.text() == "Playing" and page.now.text() == "Jump · 7 colours"


def test_not_playing_says_so(page, ctx, client):
    push(ctx, client, mode="solid")
    assert page.playing.text() == "Not playing"
