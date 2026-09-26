"""deskglow.model.presets: typed access to the generated controller presets."""
import importlib.util
import json
from pathlib import Path

import pytest

from deskglow.model import presets, presets_gen

ROOT = Path(__file__).resolve().parents[2]
PRESETS_DIR = ROOT / "presets" / "controllers"
REAL = json.loads((PRESETS_DIR / "elk-bledom.json").read_text())


def load_gen():
    spec = importlib.util.spec_from_file_location(
        "deskglow_gen_presets_for_model_tests", ROOT / "scripts" / "gen_presets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_preset_is_elk_bledom():
    p = presets.get_preset()
    assert p.id == presets.DEFAULT_PRESET_ID == "elk-bledom"
    assert presets.get_preset("elk-bledom") == p


def test_unknown_preset_id_is_a_keyerror_naming_the_known_ones():
    with pytest.raises(KeyError, match="elk-bledom"):
        presets.get_preset("triones")


def test_preset_ids_lists_every_generated_preset():
    assert presets.preset_ids() == list(presets_gen.PRESETS) == ["elk-bledom"]


def test_effect_names_are_in_table_order():
    assert presets.get_preset().effect_names() == list(REAL["effects"])


def test_match_rules_come_from_the_preset():
    p = presets.get_preset()
    assert p.service_uuids == ("0000fff0-0000-1000-8000-00805f9b34fb",)
    assert p.name_hints == tuple(REAL["match"]["name_hints"])


def test_returned_tables_are_copies():
    """A caller mutating its preset must not corrupt everyone else's."""
    a = presets.get_preset()
    a.effects["disco"] = 1
    a.ranges["r"] = (9, 9)
    b = presets.get_preset()
    assert "disco" not in b.effects
    assert b.ranges["r"] == (0, 255)


def test_preset_is_frozen():
    with pytest.raises(AttributeError):
        presets.get_preset().write_uuid = "x"


def test_generated_module_matches_the_json_sources():
    """The checked-in presets_gen.py is exactly what the generator produces."""
    gen = load_gen()
    assert gen.load_all(PRESETS_DIR) == presets_gen.PRESETS
    with open(presets_gen.__file__, encoding="utf-8") as f:
        assert f.read() == gen.render(gen.load_all(PRESETS_DIR))
