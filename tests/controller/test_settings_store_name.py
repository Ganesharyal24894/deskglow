"""SettingsStore keeps the strip's advertised name next to its address (the
macOS driver finds the strip by name when a saved CoreBluetooth UUID is foreign)."""
from fakes import FakeStorage

from deskglow.controller.settings import SettingsStore


def test_set_address_saves_the_name_too():
    storage = FakeStorage()
    SettingsStore(storage).set_address("AA:BB:CC:DD:EE:FF", "ELK-BLEDOM")
    assert storage.config == {"address": "AA:BB:CC:DD:EE:FF", "name": "ELK-BLEDOM"}
    assert SettingsStore(storage).get_device_name() == "ELK-BLEDOM"


def test_a_new_address_without_a_name_drops_the_old_name():
    storage = FakeStorage({"address": "11:11:11:11:11:11", "name": "OLD"})
    SettingsStore(storage).set_address("AA:BB:CC:DD:EE:FF")
    assert storage.config == {"address": "AA:BB:CC:DD:EE:FF"}


def test_the_unknown_placeholder_is_not_saved_as_a_name():
    storage = FakeStorage()
    SettingsStore(storage).set_address("AA:BB:CC:DD:EE:FF", "(unknown)")
    assert "name" not in storage.config


def test_forget_clears_address_and_name_but_keeps_other_keys():
    storage = FakeStorage({"address": "AA:BB:CC:DD:EE:FF", "name": "ELK", "other": 1})
    SettingsStore(storage).forget()
    assert storage.config == {"other": 1}
