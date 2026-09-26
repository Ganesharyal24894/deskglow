"""deskglow.controller.settings.SettingsStore: where the strip address comes
from, and how saved state is completed with defaults."""
import pytest
from fakes import FakeStorage

from deskglow.controller.settings import SettingsStore
from deskglow.drivers.storage_linux import LinuxStorage
from deskglow.model.settings import DEFAULTS


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def store(storage):
    return SettingsStore(storage)


# ------------------------------------------------------------ address -------

def test_get_address_is_none_when_nothing_is_configured(store):
    """Unset everywhere -> None, which is what makes the CLI suggest `setup`."""
    assert store.get_address() is None


def test_get_address_reads_saved_config(store):
    """With no env override the saved address is used."""
    store.set_address("AA:BB:CC:DD:EE:FF")
    assert store.get_address() == "AA:BB:CC:DD:EE:FF"


def test_env_address_beats_saved_config(store, storage):
    """The environment override wins over whatever is on disk."""
    store.set_address("AA:BB:CC:DD:EE:FF")
    storage.override = "00:11:22:33:44:55"
    assert store.get_address() == "00:11:22:33:44:55"


def test_env_address_works_without_a_saved_config(store, storage):
    """The env override alone is enough -- no config file required."""
    storage.override = "00:11:22:33:44:55"
    assert storage.config == {}
    assert store.get_address() == "00:11:22:33:44:55"


def test_empty_env_address_falls_back_to_saved_config(store, storage):
    """An empty override is not an address; the saved one still wins."""
    store.set_address("AA:BB:CC:DD:EE:FF")
    storage.override = ""
    assert store.get_address() == "AA:BB:CC:DD:EE:FF"


def test_set_address_persists(store, storage):
    """set_address writes through to storage."""
    store.set_address("DE:AD:BE:EF:00:01")
    assert storage.load_config()["address"] == "DE:AD:BE:EF:00:01"


def test_set_address_preserves_other_keys(store, storage):
    """Setting the address must not wipe unrelated settings."""
    storage.save_config({"nickname": "desk", "brightness_cap": 80})
    store.set_address("DE:AD:BE:EF:00:01")
    assert storage.load_config() == {
        "nickname": "desk", "brightness_cap": 80, "address": "DE:AD:BE:EF:00:01",
    }


def test_set_address_can_be_changed(store):
    """Re-running setup replaces the stored address."""
    store.set_address("AA:AA:AA:AA:AA:AA")
    store.set_address("BB:BB:BB:BB:BB:BB")
    assert store.get_address() == "BB:BB:BB:BB:BB:BB"


def test_address_precedence_with_real_linux_storage(tmp_path):
    """End to end over files + env: DESKGLOW_ADDRESS beats the saved config,
    an empty value falls back to it, and set_address survives a reload."""
    env = {}
    store = SettingsStore(LinuxStorage(home=str(tmp_path), env=env))
    assert store.get_address() is None
    store.set_address("AA:BB:CC:DD:EE:FF")
    again = SettingsStore(LinuxStorage(home=str(tmp_path), env=env))
    assert again.get_address() == "AA:BB:CC:DD:EE:FF"
    env["DESKGLOW_ADDRESS"] = "00:11:22:33:44:55"
    assert again.get_address() == "00:11:22:33:44:55"
    env["DESKGLOW_ADDRESS"] = ""
    assert again.get_address() == "AA:BB:CC:DD:EE:FF"


# -------------------------------------------------------------- state -------

def test_load_state_returns_defaults_when_missing(store):
    """No saved state -> the full DEFAULTS dict."""
    assert store.load_state() == DEFAULTS


def test_load_state_merges_saved_over_defaults(store, storage):
    storage.state = {"mode": "screen", "max_brightness": 42}
    s = store.load_state()
    assert s["mode"] == "screen" and s["max_brightness"] == 42
    assert s["screen_style"] == DEFAULTS["screen_style"]


def test_save_then_load_state_round_trip(store):
    state = dict(DEFAULTS, mode="pattern", args={"name": "fade-blue", "speed": 12})
    store.save_state(state)
    assert store.load_state() == state


def test_corrupt_state_file_boots_with_defaults(tmp_path):
    """Real storage: a truncated state file must not stop the daemon booting."""
    ls = LinuxStorage(home=str(tmp_path), env={})
    ls.save_state({"mode": "calm"})
    with open(ls.state_file, "w") as f:
        f.write('{"mode": "sol')
    assert SettingsStore(ls).load_state() == DEFAULTS
