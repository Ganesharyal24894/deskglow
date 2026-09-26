"""scripts/gen_presets.py rejects malformed presets with exit 2 and a message
naming the file and the problem."""
import copy

import pytest
from gen_support import REAL, load_gen, run_script, write_preset


def _mut(fn):
    raw = copy.deepcopy(REAL)
    fn(raw)
    return raw


def _set(path, value):
    def fn(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return fn


def _del(path):
    def fn(raw):
        node = raw
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]
    return fn


CASES = {
    "missing key": (_del(["gatt"]), "missing keys"),
    "unknown key": (_set(["colour"], 1), "unknown keys"),
    "id != file name": (_set(["id"], "other"), "id must equal"),
    "bad uuid": (_set(["gatt", "write"], "fff3"), "UUID"),
    "bad frame token": (_set(["frames", "power_on"], "7E 00 04 XY 00 01 FF 00 EF"), "bad token"),
    "color missing {b}": (_set(["frames", "color"], "7E 00 05 03 {r} {g} 00 00 EF"),
                          "needs placeholders"),
    "placeholder without range": (_set(["frames", "speed"], "7E 00 02 {speed} {x} 00 00 00 EF"),
                                  "has no range"),
    "range over a byte": (_set(["ranges", "effect"], [0, 256]), "one byte"),
    "range reversed": (_set(["ranges", "speed"], [100, 0]), "lo <= hi"),
    "effect outside range": (_set(["ranges", "effect"], [0, 100]), "outside"),
    "duplicate effect ids": (_set(["effects", "jump-colors"], "0x87"), "duplicate effect ids"),
    "default effect missing": (_set(["default_effect"], "disco"), "default_effect"),
    "missing frame": (_del(["frames", "speed"]), "frames must be exactly"),
    "effect name not a slug": (_set(["effects", "Fade Red"], "0x70"), "not a slug"),
    "empty effects": (_set(["effects"], {}), "non-empty"),
    "empty name hints entry": (_set(["match", "name_hints"], ["ELK", ""]), "name_hints"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_validate_rejects(case):
    fn, message = CASES[case]
    gen = load_gen()
    with pytest.raises(gen.PresetError) as exc:
        gen.validate(_mut(fn), "elk-bledom")
    assert message in str(exc.value)
    assert "elk-bledom.json" in str(exc.value)


def test_the_real_preset_is_accepted_by_validate():
    assert load_gen().validate(copy.deepcopy(REAL), "elk-bledom")["id"] == "elk-bledom"


def test_the_script_exits_2_with_a_message_on_an_invalid_preset(tmp_path):
    presets = write_preset(tmp_path / "presets", _mut(_del(["frames", "color"])))
    r = run_script("--presets-dir", str(presets), "--out", str(tmp_path / "out.py"))
    assert r.returncode == 2
    assert "invalid preset" in r.stderr and "elk-bledom.json" in r.stderr
    assert not (tmp_path / "out.py").exists(), "nothing is written for a bad preset"


def test_invalid_json_is_reported(tmp_path):
    presets = tmp_path / "presets"
    presets.mkdir()
    (presets / "broken.json").write_text("{not json")
    r = run_script("--check", "--presets-dir", str(presets))
    assert r.returncode == 2
    assert "broken.json" in r.stderr and "invalid JSON" in r.stderr


def test_an_empty_presets_dir_is_an_error(tmp_path):
    (tmp_path / "presets").mkdir()
    r = run_script("--presets-dir", str(tmp_path / "presets"), "--out", str(tmp_path / "o.py"))
    assert r.returncode == 2
    assert "no presets found" in r.stderr


def test_a_non_object_top_level_is_rejected():
    gen = load_gen()
    with pytest.raises(gen.PresetError, match="top level"):
        gen.validate([1, 2], "elk-bledom")
