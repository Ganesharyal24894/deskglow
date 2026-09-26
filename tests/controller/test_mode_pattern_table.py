"""Patterns mode: the built-in effect table (from the generated preset) and
how a pattern name / speed is selected. A wrong effect id silently plays the
wrong animation, so the table is pinned exactly."""
import pytest

from deskglow.controller.modes.patterns import DEFAULT, EFFECTS, Patterns, pattern_names

# The documented ELK/MELK built-in effect table: 0x87..0x9C, contiguous.
DOCUMENTED = {
    "jump-rgb": 0x87,
    "jump-colors": 0x88,
    "fade-rgb": 0x89,
    "fade-colors": 0x8A,
    "fade-red": 0x8B,
    "fade-green": 0x8C,
    "fade-blue": 0x8D,
    "fade-yellow": 0x8E,
    "fade-cyan": 0x8F,
    "fade-magenta": 0x90,
    "fade-white": 0x91,
    "fade-red-green": 0x92,
    "fade-red-blue": 0x93,
    "fade-green-blue": 0x94,
    "blink-colors": 0x95,
    "blink-red": 0x96,
    "blink-green": 0x97,
    "blink-blue": 0x98,
    "blink-yellow": 0x99,
    "blink-cyan": 0x9A,
    "blink-magenta": 0x9B,
    "blink-white": 0x9C,
}


# ---------------------------------------------------------------- the table --

def test_effect_table_matches_the_documented_ids():
    """A wrong id here plays a different animation with no error anywhere."""
    assert EFFECTS == DOCUMENTED


def test_effect_ids_cover_0x87_to_0x9c_with_no_gaps_or_duplicates():
    ids = sorted(EFFECTS.values())
    assert ids == list(range(0x87, 0x9C + 1))
    assert len(set(EFFECTS.values())) == len(EFFECTS)


def test_pattern_names_lists_every_effect_in_table_order():
    """`deskglow patterns` must show the whole set."""
    assert pattern_names() == list(EFFECTS)
    assert set(pattern_names()) == set(DOCUMENTED)


def test_default_pattern_exists_in_the_table():
    assert DEFAULT in EFFECTS


# --------------------------------------------------------------- selection --

@pytest.mark.parametrize("name,eid", sorted(DOCUMENTED.items()))
def test_each_name_selects_its_effect_id(name, eid):
    m = Patterns(name, 50)
    assert m.pattern == name
    assert m.effect_id == eid


@pytest.mark.parametrize("bad", ["nope", "", None, "JUMP-RGB", 0x87, "fade colors"])
def test_unknown_pattern_falls_back_to_the_default(bad):
    """A typo must give the default effect, not a crash or a blank strip."""
    m = Patterns(bad, 50)
    assert m.pattern == DEFAULT
    assert m.effect_id == EFFECTS[DEFAULT]


@pytest.mark.parametrize("given,expected", [
    (0, 1), (-5, 1), (1, 1), (50, 50), (100, 100), (101, 100), (9999, 100),
    ("75", 75), (42.9, 42),
])
def test_speed_is_clamped_to_1_100(given, expected):
    """The wire field is a percentage; 0 or 200 would be nonsense to the strip."""
    assert Patterns("fade-rgb", given).speed == expected
