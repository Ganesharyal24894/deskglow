"""Optional modes: screen and audio need extra packages, imported on demand.

A missing extra must surface as ModeUnavailable (a ValueError, so the daemon
treats it like any bad mode) naming the `deskglow[...]` extra to install.
"""
import sys

import pytest

from deskglow.controller import modes


def test_extras_map_each_optional_mode_to_its_pip_extra():
    assert modes.EXTRAS == {"screen": "screen", "audio": "audio"}


@pytest.mark.parametrize("name", ["screen", "audio"])
def test_a_missing_extra_names_the_deskglow_extra_to_install(monkeypatch, name):
    # None in sys.modules makes the lazy `from .<name> import ...` raise ImportError
    monkeypatch.setitem(sys.modules, f"deskglow.controller.modes.{name}", None)
    with pytest.raises(modes.ModeUnavailable) as exc:
        modes.build(name, {})
    assert f"pip install 'deskglow[{name}]'" in str(exc.value)
    assert isinstance(exc.value, ValueError)


@pytest.mark.parametrize("name", ["solid", "calm", "pattern", "circadian", "pomodoro"])
def test_core_modes_never_need_an_extra(monkeypatch, name):
    """Blocking the optional modules must not affect any core mode."""
    for opt in ("screen", "audio"):
        monkeypatch.setitem(sys.modules, f"deskglow.controller.modes.{opt}", None)
    assert modes.build(name, {}).name == name
