"""deskglow.drivers.storage_linux.LinuxStorage: JSON files under ~/.config/deskglow.

Every test uses a home directory inside tmp_path, so ~/.config is never touched.
"""
import json
import os

import pytest

from deskglow.drivers.storage_linux import LinuxStorage


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def store(home):
    return LinuxStorage(home=str(home), env={})


@pytest.fixture
def cfg_dir(home):
    return home / ".config" / "deskglow"


# ------------------------------------------------------------------ paths ----

def test_files_live_under_dot_config_deskglow(store, cfg_dir):
    assert store.config_dir() == str(cfg_dir)
    assert store.config_file == str(cfg_dir / "config.json")
    assert store.state_file == str(cfg_dir / "state.json")
    assert store.log_path() == str(cfg_dir / "daemon.log")


def test_without_home_platformdirs_decides(tmp_path):
    """Without an explicit home the (Linux) platformdirs config dir is used."""
    dirs = type("Dirs", (), {"user_config_dir": str(tmp_path / "xdg" / "deskglow")})()
    assert LinuxStorage(env={}, dirs=dirs).config_dir() == str(tmp_path / "xdg" / "deskglow")


# ------------------------------------------------------------- config -------

def test_load_config_returns_empty_dict_when_missing(store):
    """No config file yet -> {} rather than an exception."""
    assert not os.path.exists(store.config_file)
    assert store.load_config() == {}


@pytest.mark.parametrize("cfg", [
    {},
    {"address": "AA:BB:CC:DD:EE:FF"},
    {"address": "AA:BB:CC:DD:EE:FF", "nickname": "desk strip", "n": 3, "flag": True},
])
def test_save_config_load_config_round_trip(store, cfg):
    """Whatever is saved comes back verbatim."""
    store.save_config(cfg)
    assert store.load_config() == cfg


def test_save_config_writes_readable_json(store):
    """The file on disk is plain JSON a human can edit."""
    store.save_config({"address": "11:22:33:44:55:66"})
    with open(store.config_file) as f:
        assert json.load(f) == {"address": "11:22:33:44:55:66"}


def test_save_config_overwrites_previous_contents(store):
    """save_config replaces the file; it does not merge."""
    store.save_config({"address": "A", "old": 1})
    store.save_config({"address": "B"})
    assert store.load_config() == {"address": "B"}


@pytest.mark.parametrize("junk", [
    "",                                   # empty file
    "{",                                  # truncated
    '{"address": "AA:BB:CC:DD:EE:F',      # truncated mid-string
    "not json at all",
    "\x00\x01\x02",
    "[1, 2]",                             # valid JSON, but not an object
])
def test_load_config_survives_corrupt_json(store, cfg_dir, junk):
    """A half-written config must degrade to {}, never crash the CLI/daemon."""
    cfg_dir.mkdir(parents=True)
    with open(store.config_file, "w") as f:
        f.write(junk)
    assert store.load_config() == {}


# -------------------------------------------------------------- state -------

def test_load_state_is_none_when_missing(store):
    """No state file -> None (the settings store then fills in DEFAULTS)."""
    assert store.load_state() is None


def test_save_state_load_state_round_trip(store):
    """A full state survives a save/load cycle unchanged."""
    state = {
        "mode": "screen",
        "args": {"style": "vivid", "fps": 20},
        "screen_monitor": "HDMI-0",
        "screen_style": "dominant",
        "max_brightness": 70,
    }
    store.save_state(state)
    assert store.load_state() == state


@pytest.mark.parametrize("junk", ["", "{", '{"mode": "sol', "garbage", "[1]", "null"])
def test_load_state_survives_corrupt_json(store, cfg_dir, junk):
    """A state file truncated by a power cut must not stop the daemon booting."""
    cfg_dir.mkdir(parents=True)
    with open(store.state_file, "w") as f:
        f.write(junk)
    assert store.load_state() is None


def test_two_load_state_calls_are_independent(store):
    """Each load_state() call hands back its own dict."""
    store.save_state({"mode": "calm", "args": {}})
    a = store.load_state()
    b = store.load_state()
    assert a == b
    a["mode"] = "changed"
    assert b["mode"] != "changed"


# ------------------------------------------------------------- writing ------

def test_save_config_creates_config_dir(store, cfg_dir):
    """save_config() makes the config dir (and parents) when it does not exist."""
    assert not cfg_dir.exists()
    store.save_config({"address": "AA:BB:CC:DD:EE:FF"})
    assert cfg_dir.is_dir()
    assert store.load_config() == {"address": "AA:BB:CC:DD:EE:FF"}


def test_save_state_creates_config_dir(store, cfg_dir):
    """save_state() makes the config dir (and parents) when it does not exist."""
    assert not cfg_dir.exists()
    store.save_state({"mode": "off"})
    assert cfg_dir.is_dir()
    assert store.load_state()["mode"] == "off"


def test_save_config_is_atomic_and_leaves_no_temp_file(store, cfg_dir):
    """save_config writes .tmp then os.replace; no stray .tmp may survive."""
    store.save_config({"address": "AA:BB:CC:DD:EE:FF"})
    assert [p.name for p in cfg_dir.iterdir() if p.name.endswith(".tmp")] == []
    assert os.path.exists(store.config_file)


def test_save_state_is_atomic_and_leaves_no_temp_file(store, cfg_dir):
    """save_state writes .tmp then os.replace; no stray .tmp may survive."""
    store.save_state({"mode": "calm"})
    assert [p.name for p in cfg_dir.iterdir() if p.name.endswith(".tmp")] == []
    assert os.path.exists(store.state_file)


def test_repeated_saves_leave_exactly_one_file_each(store, cfg_dir):
    """Rewriting many times must not accumulate temp files."""
    for i in range(5):
        store.save_config({"address": f"AA:BB:CC:DD:EE:{i:02X}"})
        store.save_state({"mode": "solid", "n": i})
    assert sorted(p.name for p in cfg_dir.iterdir()) == ["config.json", "state.json"]


def test_save_never_leaves_a_truncated_file_visible(store):
    """The real file is only ever replaced whole, so a reader sees valid JSON."""
    store.save_state({"mode": "screen", "args": {"style": "edge"}})
    with open(store.state_file) as f:
        json.load(f)          # must parse
    store.save_state({"mode": "off"})
    with open(store.state_file) as f:
        assert json.load(f)["mode"] == "off"


# ------------------------------------------------------ address override ----

def test_address_override_reads_deskglow_address():
    assert LinuxStorage(env={"DESKGLOW_ADDRESS": "00:11:22:33:44:55"}) \
        .address_override() == "00:11:22:33:44:55"


@pytest.mark.parametrize("env", [{}, {"DESKGLOW_ADDRESS": ""}, {"SC295_ADDRESS": "00:11"}])
def test_address_override_is_none_when_unset_empty_or_legacy_name(env):
    """Only DESKGLOW_ADDRESS counts; the old SC295_ADDRESS is no longer read."""
    assert LinuxStorage(env=env).address_override() is None
