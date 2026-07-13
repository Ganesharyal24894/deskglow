"""Paths, defaults, persisted daemon state, and the configured strip address."""
import json
import os

_HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(_HOME, ".config", "sc295")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def get_address():
    """The strip's MAC. Env override wins, then the saved config. None if unset
    (the CLI/GUI then prompt `setup` to discover it)."""
    return os.environ.get("SC295_ADDRESS") or load_config().get("address")


def set_address(addr):
    cfg = load_config()
    cfg["address"] = addr
    save_config(cfg)


def socket_path():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and os.path.isdir(runtime):
        return os.path.join(runtime, "sc295d.sock")
    return f"/tmp/sc295d-{os.getuid()}.sock"


# Connection behaviour tuned to coexist with a BT speaker:
#  - never keep scanning; only a short scan when we must (re)connect
#  - keep the link only while a live mode runs; drop it after idle when off
WRITE_MIN_INTERVAL = 0.05     # <=20 writes/s to the strip (tiny BLE airtime)
SCAN_TIMEOUT = 12.0
IDLE_DISCONNECT = 30.0        # seconds of "off" before releasing the radio

DEFAULTS = {
    "mode": "off",
    "args": {},
    "screen_monitor": "focus",   # focus | HDMI-0 | eDP-1-1 | both
    "screen_style": "vivid",     # average | vivid | dominant | edge
    "max_brightness": 100,       # global ceiling (%)
}


def load_state():
    try:
        with open(STATE_FILE) as f:
            s = dict(DEFAULTS)
            s.update(json.load(f))
            return s
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save_state(state):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)
