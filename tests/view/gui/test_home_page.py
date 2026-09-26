"""Home screen: every control sends the right request; status updates the view."""
import pytest
from gui_fakes import push
from PySide6.QtCore import QPoint, Qt

from deskglow.view.gui import accent
from deskglow.view.gui.screens.home import HomePage


@pytest.fixture
def page(qtbot, ctx, client):
    p = HomePage(ctx)
    qtbot.addWidget(p)
    p.resize(824, 720)
    p.show()
    push(ctx, client)
    client.requests.clear()
    return p


def click(qtbot, widget, pos=None):
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=pos or widget.rect().center())


def test_status_fills_in_the_header_and_colour(page):
    assert page.title.text() == "Desk strip"
    assert page.state.text() == "Warm white · 80%"
    assert page.power.text() == "On" and page.power.kind == "primary"
    assert page.colour["hex"].text() == "#FFB46E"
    assert page.bri.slider.value() == 80 and page.bri.value.text() == "80%"
    assert accent.accent() == "#FFB46E"


def test_status_update_off(page, ctx, client):
    push(ctx, client, mode="off", color=None)
    assert page.state.text() == "Off"
    assert page.power.text() == "Off" and page.power.kind == "raised"
    assert page.preview.on is False


def test_clicking_a_swatch_sets_that_solid_colour(qtbot, page, client):
    red = page.colour["swatches"].buttons[2]
    click(qtbot, red)
    assert client.sent() == [{"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 59, 48]}}]
    assert client.requests[-1] == {"cmd": "status"}, "the view refreshes after a change"


def test_the_current_colour_swatch_is_selected(page, ctx, client):
    push(ctx, client, color="#3DDC97", args={"rgb": [61, 220, 151]})
    selected = [b.colour for b in page.colour["swatches"].buttons if b.selected]
    assert selected == ["#3DDC97"]


def test_power_toggles_off_and_on(qtbot, page, ctx, client):
    click(qtbot, page.power)
    assert client.sent() == [{"cmd": "off"}]
    push(ctx, client, mode="off")
    click(qtbot, page.power)
    assert client.sent()[-1] == {"cmd": "on"}


def test_reset(qtbot, page, client):
    click(qtbot, page.reset)
    assert client.sent() == [{"cmd": "reset"}]


def test_brightness_slider_sets_the_level(page, client):
    page.bri.slider.setValue(35)
    assert client.sent() == [{"cmd": "config", "key": "brightness", "value": 35}]
    assert page.bri.value.text() == "35%"


def test_status_does_not_fight_a_dragged_slider(page, ctx, client):
    page.bri.slider.setSliderDown(True)
    page.bri.slider.setValue(20)
    push(ctx, client, brightness=80)
    assert page.bri.slider.value() == 20
    page.bri.slider.setSliderDown(False)


def test_save_as_favourite_adds_the_current_colour(qtbot, page, client):
    click(qtbot, page.colour["save"])
    assert client.sent() == [{"cmd": "favourite_add", "color": "#FFB46E"}]


def test_removing_a_favourite(page, client):
    page.colour["swatches"].remove.emit("#FF3B30")
    assert client.sent() == [{"cmd": "favourite_remove", "color": "#FF3B30"}]


def test_favourites_from_status_replace_the_swatches(page, ctx, client):
    push(ctx, client, favourites=["#123456", "#FFB46E"])
    assert [b.colour for b in page.colour["swatches"].buttons] == ["#123456", "#FFB46E"]


@pytest.mark.parametrize("tile,mode", [("screen", "screen"), ("audio", "audio"),
                                       ("calm", "calm"), ("circadian", "circadian"),
                                       ("effects", "pattern"), ("focus", "pomodoro")])
def test_mode_tiles_start_their_mode(qtbot, page, client, tile, mode):
    click(qtbot, page.tiles[tile])
    assert client.sent()[0]["mode"] == mode


def test_the_running_mode_tile_is_highlighted(page, ctx, client):
    push(ctx, client, mode="calm", color="#5A8CAA")
    assert [t for t, w in page.tiles.items() if w.active] == ["calm"]
    push(ctx, client, mode="off")
    assert not any(w.active for w in page.tiles.values())


def test_effects_tile_restarts_the_last_effect_seen(qtbot, page, ctx, client):
    push(ctx, client, mode="pattern", args={"name": "blink-blue", "speed": 12}, color=None)
    push(ctx, client, mode="solid", args={"rgb": [1, 1, 1]})
    client.requests.clear()
    click(qtbot, page.tiles["effects"])
    assert client.sent()[0]["args"] == {"name": "blink-blue", "speed": 12}


def test_clicking_the_hue_ring_band_picks_that_colour(qtbot, page, client):
    ring = page.colour["ring"]
    click(qtbot, ring, QPoint(64, 11))              # top of the band: red
    assert client.sent() == [{"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 59, 48]}}]


def test_clicking_the_middle_of_the_ring_does_nothing(qtbot, page, client):
    click(qtbot, page.colour["ring"], QPoint(64, 64))
    assert client.sent() == []


def test_power_button_glows_only_when_on(page, ctx, client):
    assert page.power.graphicsEffect().isEnabled()
    push(ctx, client, mode="off")
    assert not page.power.graphicsEffect().isEnabled()
