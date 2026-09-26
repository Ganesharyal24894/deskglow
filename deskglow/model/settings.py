"""The daemon's settings schema: defaults, the keys a client may change, their
validation, and the connection-tuning constants. Pure data, no I/O."""
import copy

from . import settings_rules

# Connection behaviour tuned to coexist with a BT speaker:
#  - never keep scanning; only a short scan when we must (re)connect
#  - keep the link only while a live mode runs; drop it after idle when off
WRITE_MIN_INTERVAL = 0.05     # <=20 writes/s to the strip (tiny BLE airtime)
SCAN_TIMEOUT = 12.0
IDLE_DISCONNECT = 30.0        # seconds of "off" before releasing the radio

SCREEN_STYLES = settings_rules.SCREEN_STYLES
THEMES = settings_rules.THEMES
MAX_FAVOURITES = settings_rules.MAX_FAVOURITES
WARM_WHITE = (255, 180, 110)
DEFAULT_FAVOURITES = ["#FFB46E", "#FFFFFF", "#FF3B30", "#FF7A1A",
                      "#3DDC97", "#00B8C7", "#5B8CFF", "#B35CFF"]

# Settings the daemon accepts over the `config` command.
CONFIG_KEYS = ("screen_monitor", "screen_style", "max_brightness", "brightness",
               "strip_name", "favourites", "sunset_on", "audio_sensitivity",
               "hotkey_on", "tray_on", "theme", "focus_timer")

DEFAULTS = {
    "mode": "off",
    "args": {},
    "screen_monitor": "focus",   # focus | both | a monitor/output name
    "screen_style": "vivid",     # average | vivid | dominant | edge
    "max_brightness": 100,       # global ceiling (%)
    "brightness": 100,           # the user's level (%), under the ceiling
    "strip_name": "Desk strip",
    "favourites": list(DEFAULT_FAVOURITES),
    "sunset_on": False,
    "audio_sensitivity": 60,     # 1-100; 60 is the audio mode's stock gain
    "hotkey_on": False,
    "tray_on": True,
    "theme": "system",           # system | dark | light
    "focus_timer": {"work": 25, "break": 5, "rounds": 4},
    "last_solid": list(WARM_WHITE),   # the last solid colour (sunset / Stop)
    "resume": None,              # {"mode", "args"} to restore on `on`
}


def validate_setting(key, value):
    """Return the value to store for `key`, or raise ValueError.

    The daemon is an IPC boundary: anything stored here is persisted and later
    used for arithmetic on every colour write, so a bad value must be rejected
    at the door rather than crashing whatever mode is running.
    """
    rule = settings_rules.RULES.get(key)
    if rule is None:
        raise ValueError(f"unknown config key {key!r}")
    return rule(value)


def state_from(saved):
    """The full daemon state: DEFAULTS topped up with whatever was `saved`.

    Deep copy: DEFAULTS holds mutable values (args), and a shallow copy would
    hand every caller the same dict to mutate, poisoning the defaults. Anything
    that is not a dict (missing or corrupt file) yields plain defaults.
    """
    state = copy.deepcopy(DEFAULTS)
    if isinstance(saved, dict):
        state.update(saved)
    return state
