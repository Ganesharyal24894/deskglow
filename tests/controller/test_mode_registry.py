"""Registry tests: deskglow.controller.modes.build() maps names+args onto Mode objects."""
import pytest

from deskglow.controller import modes
from deskglow.controller.modes.calm import Calm
from deskglow.controller.modes.circadian import Circadian
from deskglow.controller.modes.patterns import EFFECTS, Patterns, pattern_names
from deskglow.controller.modes.pomodoro import Pomodoro
from deskglow.controller.modes.solid import Solid

EXPECTED_CLASS = {
    "solid": "Solid",
    "screen": "Screen",
    "calm": "Calm",
    "pattern": "Patterns",
    "circadian": "Circadian",
    "pomodoro": "Pomodoro",
    "audio": "Audio",
}


def test_mode_names_is_the_public_list_of_buildable_modes():
    """Every advertised name must actually build; the list must have no dupes."""
    assert len(set(modes.MODE_NAMES)) == len(modes.MODE_NAMES), "duplicate mode name"
    assert set(modes.MODE_NAMES) == set(EXPECTED_CLASS)


@pytest.mark.parametrize("name", list(EXPECTED_CLASS))
def test_build_returns_the_right_class_for_every_mode_name(name):
    """build() maps each advertised name onto its own Mode subclass."""
    m = modes.build(name, {})
    assert type(m).__name__ == EXPECTED_CLASS[name]
    assert isinstance(m, modes.Mode)


@pytest.mark.parametrize("name", list(EXPECTED_CLASS))
def test_built_mode_reports_its_own_name(name):
    """The instance's .name is what the daemon records as the running mode."""
    assert modes.build(name, {}).name == name


@pytest.mark.parametrize("name", list(EXPECTED_CLASS))
def test_build_is_case_insensitive(name):
    """Users type `deskglow SOLID`; the registry must not care about case."""
    assert type(modes.build(name.upper(), {})).__name__ == EXPECTED_CLASS[name]
    assert type(modes.build(name.capitalize(), {})).__name__ == EXPECTED_CLASS[name]


@pytest.mark.parametrize("bad", ["nope", "", None, "solidd", "off", "screen "])
def test_build_rejects_unknown_names_with_valueerror(bad):
    """An unknown mode is a caller error, reported as ValueError (not KeyError)."""
    with pytest.raises(ValueError):
        modes.build(bad, {})


def test_build_tolerates_missing_args_dict():
    """args=None is treated as an empty dict rather than exploding."""
    assert modes.build("calm", None).name == "calm"
    assert modes.build("solid", None).rgb == (255, 180, 110)


# ---------------------------------------------------------------- defaults --

def test_solid_defaults_to_the_documented_warm_white():
    """Documented default for `deskglow color` with no colour given."""
    assert modes.build("solid", {}).rgb == (255, 180, 110)


def test_pattern_defaults_to_fade_colors_at_speed_50():
    """Documented pattern defaults."""
    m = modes.build("pattern", {})
    assert (m.pattern, m.speed) == ("fade-colors", 50)
    assert m.effect_id == EFFECTS["fade-colors"]


def test_pomodoro_defaults_to_25_5_x4():
    """The classic pomodoro: 25m focus, 5m break, 4 rounds."""
    m = modes.build("pomodoro", {})
    assert (m.work, m.brk, m.rounds) == (25.0, 5.0, 4)


def test_audio_defaults_to_system_source_with_drifting_hue():
    """No rgb/target given => hue drifts, capture the system (sink) output."""
    m = modes.build("audio", {})
    assert m.base is None
    assert m.target is None
    assert m.source == "system"


# ------------------------------------------------------------ pass-through --

def test_solid_passes_rgb_through():
    assert modes.build("solid", {"rgb": [1, 2, 3]}).rgb == (1, 2, 3)


def test_pattern_passes_name_and_speed_through():
    m = modes.build("pattern", {"name": "blink-white", "speed": 7})
    assert m.pattern == "blink-white"
    assert m.effect_id == EFFECTS["blink-white"]
    assert m.speed == 7


def test_pattern_with_unknown_name_falls_back_to_the_default_effect():
    m = modes.build("pattern", {"name": "disco-inferno"})
    assert m.pattern == "fade-colors"


def test_pomodoro_passes_work_break_rounds_through():
    """Note the arg key is `break` (a Python keyword), mapped onto brk."""
    m = modes.build("pomodoro", {"work": 50, "break": 10, "rounds": 2})
    assert (m.work, m.brk, m.rounds) == (50.0, 10.0, 2)


def test_audio_passes_rgb_target_and_source_through():
    m = modes.build("audio", {"rgb": [10, 20, 30], "target": "sink.monitor",
                              "source": "mic"})
    assert m.base == (10, 20, 30)
    assert m.target == "sink.monitor"
    assert m.source == "mic"


def test_audio_rejects_an_unknown_source_and_falls_back_to_system():
    assert modes.build("audio", {"source": "telepathy"}).source == "system"


def test_extra_args_are_ignored_rather_than_fatal():
    """Old daemon state can carry args a newer mode no longer understands."""
    assert modes.build("calm", {"rgb": [1, 2, 3], "speed": 9}).name == "calm"


# ---------------------------------------------------------------- describe --

@pytest.mark.parametrize("name", list(EXPECTED_CLASS))
def test_describe_returns_a_useful_non_empty_string(name):
    """describe() is shown by `deskglow status`, so it must always say something."""
    d = modes.build(name, {}).describe()
    assert isinstance(d, str)
    assert d.strip()


def test_describe_includes_the_distinguishing_arguments():
    """Two differently-configured instances must not describe identically."""
    assert modes.build("solid", {"rgb": [1, 2, 3]}).describe() != \
        modes.build("solid", {"rgb": [4, 5, 6]}).describe()
    assert modes.build("pattern", {"name": "blink-red"}).describe() != \
        modes.build("pattern", {"name": "fade-blue"}).describe()
    assert modes.build("pomodoro", {"work": 25}).describe() != \
        modes.build("pomodoro", {"work": 50}).describe()


def test_describe_mentions_the_actual_values():
    assert "blink-red" in modes.build("pattern", {"name": "blink-red", "speed": 3}).describe()
    assert "3" in modes.build("pattern", {"name": "blink-red", "speed": 3}).describe()
    assert "50" in modes.build("pomodoro", {"work": 50, "break": 10, "rounds": 2}).describe()
    assert "mic" in modes.build("audio", {"source": "mic"}).describe()


def test_pattern_names_lists_every_effect():
    """`deskglow patterns` reads this; it must cover the whole table."""
    assert pattern_names() == list(EFFECTS)
    assert len(pattern_names()) == len(EFFECTS)
    for n in pattern_names():
        assert modes.build("pattern", {"name": n}).pattern == n


def test_registry_reexports_the_pieces_the_daemon_imports():
    """The daemon imports these names from deskglow.controller.modes; keep them public."""
    for attr in ("Mode", "ModeContext", "build", "MODE_NAMES", "pattern_names"):
        assert hasattr(modes, attr)
    assert issubclass(Solid, modes.Mode)
    assert issubclass(Calm, modes.Mode)
    assert issubclass(Circadian, modes.Mode)
    assert issubclass(Patterns, modes.Mode)
    assert issubclass(Pomodoro, modes.Mode)
