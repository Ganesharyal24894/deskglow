"""vm.effects (tiles from the preset table) and vm.sync (diagram, chips, meter)."""
import pytest
from gui_fakes import MONITORS, status

from deskglow.model.presets import get_preset
from deskglow.view.gui.vm import effects, sync
from deskglow.view.gui.vm.status import StatusView

ALL = effects.effects(get_preset().effect_names())


def test_one_tile_per_preset_effect_in_table_order():
    assert [e.id for e in ALL] == get_preset().effect_names()
    assert len(ALL) == 22


@pytest.mark.parametrize("fid,count", [("all", 22), ("fade", 12), ("jump", 2), ("blink", 8)])
def test_filters(fid, count):
    assert len(effects.visible(ALL, fid)) == count


@pytest.mark.parametrize("eid,label", [
    ("jump-rgb", "Jump · RGB"), ("jump-colors", "Jump · 7 colours"),
    ("fade-red", "Fade · Red"), ("fade-red-green", "Fade · Red & Green"),
    ("blink-colors", "Blink · 7 colours"), ("blink-white", "Blink · White"),
])
def test_labels_follow_the_design(eid, label):
    assert effects.describe(eid).label == label


def test_previews_follow_the_design():
    jump = effects.describe("jump-rgb").stops
    assert jump[0] == (0.0, "#FF3B30") and jump[1][1] == "#FF3B30"   # hard stops
    assert effects.describe("fade-red").stops == ((0.0, "fx_dark"), (0.5, "#FF3B30"),
                                                  (1.0, "fx_dark"))
    assert [c for _p, c in effects.describe("fade-red-blue").stops] == [
        "#FF3B30", "#1E7BFF", "#FF3B30"]
    blink = effects.describe("blink-red").stops
    assert len(blink) == 16 and blink[2] == (pytest.approx(0.1375), "blink_gap")


def test_unknown_names_still_get_a_tile():
    e = effects.describe("sparkle-gold")
    assert e.kind == "fade" and e.stops


def test_play_request_clamps_speed():
    assert effects.play("fade-red", 0) == {"cmd": "set_mode", "mode": "pattern",
                                           "args": {"name": "fade-red", "speed": 1}}


def test_boxes_are_scaled_left_to_right():
    boxes = sync.boxes({"B": dict(MONITORS["HDMI-1"]), "A": dict(MONITORS["DP-1"])})
    assert [b.name for b in boxes] == ["A", "B"]
    assert (boxes[0].width, boxes[0].height) == (150, 96)
    assert boxes[1].height == 72 and boxes[1].resolution == "1920 × 1080"
    assert sync.boxes({}) == []


def test_targets_and_lit_monitors():
    assert [t for t, _l in sync.targets(MONITORS)] == ["focus", "both", "DP-1", "HDMI-1"]
    assert sync.lit("both", "HDMI-1", MONITORS)
    assert sync.lit("focus", "DP-1", MONITORS) and not sync.lit("focus", "HDMI-1", MONITORS)
    assert sync.lit("HDMI-1", "HDMI-1", MONITORS) and not sync.lit("HDMI-1", "DP-1", MONITORS)
    assert sync.primary({"X": {"left": 5, "top": 5, "width": 1, "height": 1}}) == "X"
    assert sync.primary({}) is None


def test_readout_only_while_screen_sync_runs():
    live = StatusView(status(mode="screen", screen={"color": "#4A7BFF", "fps": 14.6}))
    assert sync.readout(live) == ("#4A7BFF", "15 fps")
    assert sync.readout(StatusView(status())) is None


def test_meter_keeps_the_last_eighteen_levels():
    m = sync.Meter()
    for v in (0.5, 2.0, -1):
        m.push(v)
    assert len(m.levels) == 18 and m.levels[-3:] == [0.5, 1.0, 0.0]
    assert min(m.heights()) == 0.06
    m.reset()
    assert m.levels == [0.0] * 18


def test_buttons_start_or_stop():
    idle = StatusView(status())
    assert sync.screen_button(idle, "edge") == (
        "Start screen sync", {"cmd": "set_mode", "mode": "screen", "args": {"style": "edge"}})
    label, req = sync.screen_button(StatusView(status(mode="screen")), "edge")
    assert label == "Stop screen sync" and req["mode"] == "solid"
    assert sync.music_button(idle, "mic")[1]["args"] == {"source": "mic"}
    assert sync.music_button(StatusView(status(mode="audio")), "mic")[0] == "Stop music sync"


def test_source_change_restarts_only_a_running_music_sync():
    running = StatusView(status(mode="audio", args={"source": "system"}))
    assert sync.source_change(running, "mic")["args"] == {"source": "mic"}
    assert sync.source_change(running, "system") is None
    assert sync.source_change(StatusView(status()), "mic") is None


def test_config_requests():
    assert sync.set_target("both") == {"cmd": "config", "key": "screen_monitor", "value": "both"}
    assert sync.set_style("edge")["key"] == "screen_style"
    assert sync.set_sensitivity(33.0)["value"] == 33
