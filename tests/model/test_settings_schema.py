"""deskglow.model.settings: the daemon's defaults, merge rule, validation and
tuning constants. Pure data; no files."""
import pytest

from deskglow.model import settings


@pytest.fixture(autouse=True)
def restore_module_defaults():
    """Deep-restore DEFAULTS after every test.

    DEFAULTS is module-level mutable state; a test that (deliberately) proves it
    can be corrupted must not leak that corruption into the rest of the suite.
    """
    snapshot = {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in settings.DEFAULTS.items()}
    yield
    settings.DEFAULTS.clear()
    settings.DEFAULTS.update(snapshot)


# ------------------------------------------------------------ defaults ------

def test_defaults_shape():
    """Pin the default daemon state the daemon boots into."""
    assert settings.DEFAULTS == {
        "mode": "off",
        "args": {},
        "screen_monitor": "focus",
        "screen_style": "vivid",
        "max_brightness": 100,
        "brightness": 100,
        "strip_name": "Desk strip",
        "favourites": ["#FFB46E", "#FFFFFF", "#FF3B30", "#FF7A1A",
                       "#3DDC97", "#00B8C7", "#5B8CFF", "#B35CFF"],
        "sunset_on": False,
        "audio_sensitivity": 60,
        "hotkey_on": False,
        "tray_on": True,
        "theme": "system",
        "focus_timer": {"work": 25, "break": 5, "rounds": 4},
        "last_solid": [255, 180, 110],
        "resume": None,
    }


def test_tuning_constants_are_sane():
    """The BLE pacing constants must stay positive and rate-limiting."""
    assert 0 < settings.WRITE_MIN_INTERVAL <= 0.2      # >= ~5 writes/s, <= 20/s
    assert settings.SCAN_TIMEOUT > 0
    assert settings.IDLE_DISCONNECT > 0


def test_config_keys_and_styles():
    assert settings.CONFIG_KEYS == (
        "screen_monitor", "screen_style", "max_brightness", "brightness", "strip_name",
        "favourites", "sunset_on", "audio_sensitivity", "hotkey_on", "tray_on", "theme",
        "focus_timer")
    assert settings.SCREEN_STYLES == ("average", "vivid", "dominant", "edge")


# ----------------------------------------------------------- state_from -----

@pytest.mark.parametrize("saved", [None, [1, 2], "junk", 3])
def test_state_from_nothing_usable_is_the_defaults(saved):
    """A missing or corrupt state file -> the full DEFAULTS dict."""
    assert settings.state_from(saved) == settings.DEFAULTS


@pytest.mark.parametrize("key", sorted(settings.DEFAULTS))
def test_state_from_always_fills_every_default_key(key):
    """A partial saved state is topped up with every missing default."""
    assert key in settings.state_from({"mode": "solid"})


def test_state_from_merges_saved_over_defaults():
    """Saved values win over defaults; unsaved keys keep their default."""
    s = settings.state_from({"mode": "screen", "max_brightness": 42})
    assert s["mode"] == "screen"
    assert s["max_brightness"] == 42
    assert s["screen_style"] == settings.DEFAULTS["screen_style"]
    assert s["screen_monitor"] == settings.DEFAULTS["screen_monitor"]


def test_state_from_does_not_mutate_the_module_defaults():
    """Reading state must never rewrite DEFAULTS for the rest of the process."""
    before = dict(settings.DEFAULTS)
    settings.state_from({"mode": "calm", "max_brightness": 5})
    assert before == settings.DEFAULTS


def test_state_from_returns_an_independent_args_dict():
    """Mutating the returned state must not leak into the module defaults."""
    state = settings.state_from(None)
    state["args"]["injected"] = True
    assert settings.DEFAULTS["args"] == {}, "DEFAULTS['args'] was mutated by a caller"


def test_two_state_from_calls_are_independent():
    a = settings.state_from(None)
    b = settings.state_from(None)
    assert a == b
    a["mode"] = "changed"
    assert b["mode"] != "changed"


# ------------------------------------------------------- validate_setting ---

@pytest.mark.parametrize("value,expected", [
    (0, 0), (100, 100), (55, 55), (150, 100), (-20, 0), (49.6, 50), (12.4, 12)])
def test_max_brightness_is_rounded_and_clamped(value, expected):
    assert settings.validate_setting("max_brightness", value) == expected


@pytest.mark.parametrize("bad", ["abc", "50", None, True, False, [50], {}])
def test_max_brightness_must_be_a_real_number(bad):
    """Strings and bools are refused: the value divides every colour write."""
    with pytest.raises(ValueError):
        settings.validate_setting("max_brightness", bad)


@pytest.mark.parametrize("style", settings.SCREEN_STYLES)
def test_every_screen_style_is_accepted(style):
    assert settings.validate_setting("screen_style", style) == style


@pytest.mark.parametrize("bad", ["VIVID", "bogus", "", None, 3])
def test_unknown_screen_style_is_refused(bad):
    with pytest.raises(ValueError, match="screen_style"):
        settings.validate_setting("screen_style", bad)


@pytest.mark.parametrize("value,expected", [
    ("focus", "focus"), ("both", "both"), ("  DP-2 ", "DP-2"), ("HDMI-A-1", "HDMI-A-1")])
def test_screen_monitor_accepts_any_name_and_strips_it(value, expected):
    assert settings.validate_setting("screen_monitor", value) == expected


@pytest.mark.parametrize("bad", ["", "   ", None, 2])
def test_screen_monitor_must_be_a_non_empty_string(bad):
    with pytest.raises(ValueError):
        settings.validate_setting("screen_monitor", bad)


def test_unknown_key_is_refused():
    with pytest.raises(ValueError, match="nope"):
        settings.validate_setting("nope", 1)
