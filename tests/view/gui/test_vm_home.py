"""vm.home: swatches, active tile, and every request Home sends."""
import pytest
from gui_fakes import status

from deskglow.view.gui.vm import home
from deskglow.view.gui.vm.status import StatusView


def test_swatches_are_the_favourites_with_the_current_colour_selected():
    sw = home.swatches(StatusView(status(color="#FF3B30")))
    assert [s.colour for s in sw][:3] == ["#FFB46E", "#FFFFFF", "#FF3B30"]
    assert [s.selected for s in sw].count(True) == 1 and sw[2].selected
    assert sw[2].name == "Red"


def test_nothing_is_selected_when_off_or_not_solid():
    assert not any(s.selected for s in home.swatches(StatusView(status(mode="off"))))
    assert not any(s.selected for s in home.swatches(StatusView(status(mode="calm"))))


@pytest.mark.parametrize("mode,tile", [("screen", "screen"), ("pattern", "effects"),
                                       ("pomodoro", "focus"), ("solid", None), ("off", None)])
def test_active_tile(mode, tile):
    assert home.active_tile(StatusView(status(mode=mode))) == tile


def test_no_active_tile_when_the_daemon_is_unreachable():
    assert home.active_tile(StatusView({"ok": False, "mode": "calm"})) is None


def test_simple_requests():
    assert home.solid("#FF7A1A") == {"cmd": "set_mode", "mode": "solid",
                                     "args": {"rgb": [255, 122, 26]}}
    assert home.power(StatusView(status())) == {"cmd": "off"}
    assert home.power(StatusView(status(mode="off"))) == {"cmd": "on"}
    assert home.brightness(42.0) == {"cmd": "config", "key": "brightness", "value": 42}
    assert home.save_favourite("#123456") == {"cmd": "favourite_add", "color": "#123456"}
    assert home.remove_favourite("#123456") == {"cmd": "favourite_remove", "color": "#123456"}


@pytest.mark.parametrize("tile,mode,args", [
    ("screen", "screen", {}), ("calm", "calm", {}), ("circadian", "circadian", {}),
    ("audio", "audio", {"source": "system"}),
    ("effects", "pattern", {"name": "fade-colors", "speed": 50}),
    ("focus", "pomodoro", {"work": 50, "break": 10, "rounds": 2}),
])
def test_tile_requests(tile, mode, args):
    s = StatusView(status(focus_timer={"work": 50, "break": 10, "rounds": 2}))
    assert home.tile_request(tile, s) == {"cmd": "set_mode", "mode": mode, "args": args}


def test_effects_tile_resumes_the_running_or_remembered_effect():
    running = StatusView(status(mode="pattern", args={"name": "blink-red", "speed": 9}))
    assert home.tile_request("effects", running)["args"] == {"name": "blink-red", "speed": 9}
    other = StatusView(status())
    assert home.tile_request("effects", other, ("fade-blue", 30))["args"] == {
        "name": "fade-blue", "speed": 30}


def test_unknown_tile_is_an_error():
    with pytest.raises(ValueError):
        home.tile_request("disco", StatusView(status()))


def test_back_to_colour_uses_the_last_solid():
    assert home.back_to_colour(StatusView(status(last_solid="#00B8C7")))["args"] == {
        "rgb": [0, 184, 199]}
