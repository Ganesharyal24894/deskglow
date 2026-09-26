"""First-run migration from the project's former name: ~/.config/sc295 is
copied to ~/.config/deskglow so an upgrade keeps the strip and last mode."""
import json

import pytest

from deskglow.controller.settings import SettingsStore
from deskglow.drivers.storage_linux import LinuxStorage

CONFIG = {"address": "AA:BB:CC:DD:EE:FF"}
STATE = {"mode": "pattern", "args": {"name": "fade-blue", "speed": 12}}


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def legacy(home):
    d = home / ".config" / "sc295"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def new_dir(home):
    return home / ".config" / "deskglow"


def _write(path, obj):
    path.write_text(json.dumps(obj))


def test_both_files_are_copied_and_the_old_dir_is_left_alone(home, legacy, new_dir):
    _write(legacy / "config.json", CONFIG)
    _write(legacy / "state.json", STATE)
    (legacy / "daemon.log").write_text("old log\n")
    copied = LinuxStorage(home=str(home), env={}).migrate_legacy()
    assert sorted(copied) == ["config.json", "state.json"]
    for name in ("config.json", "state.json"):
        assert (new_dir / name).read_bytes() == (legacy / name).read_bytes()
    assert not (new_dir / "daemon.log").exists(), "only config/state migrate"
    assert sorted(p.name for p in legacy.iterdir()) == [
        "config.json", "daemon.log", "state.json"], "legacy dir must be untouched"


def test_only_the_files_that_exist_are_copied(home, legacy, new_dir):
    _write(legacy / "config.json", CONFIG)
    assert LinuxStorage(home=str(home), env={}).migrate_legacy() == ["config.json"]
    assert (new_dir / "config.json").exists()
    assert not (new_dir / "state.json").exists()


def test_an_existing_deskglow_dir_is_never_overwritten(home, legacy, new_dir):
    """Migration runs once: after that the new dir is the source of truth."""
    _write(legacy / "config.json", CONFIG)
    new_dir.mkdir(parents=True)
    _write(new_dir / "config.json", {"address": "11:22:33:44:55:66"})
    assert LinuxStorage(home=str(home), env={}).migrate_legacy() == []
    assert json.loads((new_dir / "config.json").read_text()) == {
        "address": "11:22:33:44:55:66"}


def test_no_legacy_dir_means_nothing_to_do(home, new_dir):
    assert LinuxStorage(home=str(home), env={}).migrate_legacy() == []
    assert not new_dir.exists(), "migration must not create the new dir needlessly"


def test_migrated_address_and_state_are_what_the_app_then_sees(home, legacy):
    _write(legacy / "config.json", CONFIG)
    _write(legacy / "state.json", STATE)
    storage = LinuxStorage(home=str(home), env={})
    storage.migrate_legacy()
    store = SettingsStore(storage)
    assert store.get_address() == "AA:BB:CC:DD:EE:FF"
    assert store.load_state()["mode"] == "pattern"
    assert store.load_state()["args"] == STATE["args"]


def test_migrating_twice_is_a_no_op(home, legacy):
    _write(legacy / "config.json", CONFIG)
    storage = LinuxStorage(home=str(home), env={})
    assert storage.migrate_legacy() == ["config.json"]
    assert storage.migrate_legacy() == []
