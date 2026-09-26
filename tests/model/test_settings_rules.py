"""deskglow.model.settings: validation of the settings the desktop app adds."""
import pytest

from deskglow.model import settings_rules as rules
from deskglow.model.settings import validate_setting


@pytest.mark.parametrize("key,value,expected", [
    ("brightness", 80, 80), ("brightness", 140, 100), ("brightness", -3, 0),
    ("audio_sensitivity", 0, 1), ("audio_sensitivity", 101, 100), ("audio_sensitivity", 60.4, 60),
    ("strip_name", "  Shelf  ", "Shelf"), ("sunset_on", True, True), ("hotkey_on", False, False),
    ("tray_on", True, True), ("theme", "light", "light"),
    ("favourites", ["#ffb46e", "#FFB46E", "#000000"], ["#FFB46E", "#000000"]),
    ("focus_timer", {"work": 50, "break": 10, "rounds": 2}, {"work": 50, "break": 10, "rounds": 2}),
    ("focus_timer", {"work": 999, "break": 0, "rounds": 99}, {"work": 180, "break": 1, "rounds": 12}),
])
def test_valid_values_are_normalised(key, value, expected):
    assert validate_setting(key, value) == expected


@pytest.mark.parametrize("key,value", [
    ("brightness", "80"), ("brightness", True), ("audio_sensitivity", None),
    ("strip_name", ""), ("strip_name", "x" * 41), ("strip_name", 5),
    ("sunset_on", 1), ("hotkey_on", "yes"), ("tray_on", None), ("theme", "blue"),
    ("favourites", "#FFFFFF"), ("favourites", ("#FFFFFF",)), ("favourites", ["red"]), ("favourites", ["#12345"]),
    ("favourites", [f"#0000{i:02X}" for i in range(9)]),
    ("focus_timer", {"work": 25, "break": 5}), ("focus_timer", [25, 5, 4]),
    ("focus_timer", "work break rounds"),
    ("focus_timer", {"work": "25", "break": 5, "rounds": 4}),
])
def test_invalid_values_are_rejected(key, value):
    with pytest.raises(ValueError):
        validate_setting(key, value)


def test_forty_character_name_is_the_limit():
    assert validate_setting("strip_name", "x" * 40) == "x" * 40


@pytest.mark.parametrize("addr,expected", [
    ("a4:c1:38:5e:22:9b", "A4:C1:38:5E:22:9B"),
    (" BE:32:57:A0:13:6C ", "BE:32:57:A0:13:6C"),
    ("0c1e5f2a-3b4c-4d5e-8f90-a1b2c3d4e5f6", "0C1E5F2A-3B4C-4D5E-8F90-A1B2C3D4E5F6"),
])
def test_addresses_accept_macs_and_macos_uuids(addr, expected):
    assert rules.address(addr) == expected


@pytest.mark.parametrize("addr", ["", "A4:C1:38:5E:22", "A4-C1-38-5E-22-9B", "zz:c1:38:5e:22:9b", None, 7])
def test_bad_addresses_are_rejected(addr):
    with pytest.raises(ValueError):
        rules.address(addr)


def test_add_favourite_puts_it_first_and_caps_at_eight():
    favs = [f"#0000{i:02X}" for i in range(8)]
    out = rules.add_favourite(favs, "#abcdef")
    assert out[0] == "#ABCDEF" and len(out) == 8 and "#000007" not in out


def test_add_existing_favourite_moves_it_to_the_front_without_duplicating():
    assert rules.add_favourite(["#111111", "#222222"], "#222222") == ["#222222", "#111111"]


def test_remove_favourite():
    assert rules.remove_favourite(["#111111", "#222222"], "#111111") == ["#222222"]
    with pytest.raises(ValueError):
        rules.remove_favourite([], "nope")
