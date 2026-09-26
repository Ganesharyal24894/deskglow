"""scripts/gen_presets.py on valid input: rendering, determinism and --check."""
import copy

from gen_support import PRESETS_DIR, REAL, ROOT, load_gen, run_script, write_preset

OUT = ROOT / "deskglow" / "model" / "presets_gen.py"


def test_the_real_presets_validate():
    presets = load_gen().load_all(PRESETS_DIR)
    assert list(presets) == ["elk-bledom"]
    p = presets["elk-bledom"]
    assert p["write_uuid"] == "0000fff3-0000-1000-8000-00805f9b34fb"
    assert p["frames"]["color"] == (0x7E, 0x00, 0x05, 0x03, "r", "g", "b", 0x00, 0xEF)
    assert p["effects"]["fade-colors"] == 0x8A


def test_render_is_deterministic_and_marked_generated():
    gen = load_gen()
    a = gen.render(gen.load_all(PRESETS_DIR))
    b = gen.render(gen.load_all(PRESETS_DIR))
    assert a == b
    assert "generated — do not edit" in a.splitlines()[0]


def test_effect_table_order_is_preserved_not_sorted():
    """The CLI lists effects in table order; the generator must not sort them."""
    p = load_gen().load_all(PRESETS_DIR)["elk-bledom"]
    assert list(p["effects"]) == list(REAL["effects"])


def test_rendered_module_is_valid_python_with_the_same_data():
    gen = load_gen()
    presets = gen.load_all(PRESETS_DIR)
    ns = {}
    exec(compile(gen.render(presets), "presets_gen", "exec"), ns)
    assert ns["PRESETS"] == presets


def test_check_passes_on_the_checked_in_file():
    r = run_script("--check")
    assert r.returncode == 0, r.stderr
    assert "up to date" in r.stdout


def test_check_fails_when_the_output_is_stale(tmp_path):
    out = tmp_path / "presets_gen.py"
    out.write_text(OUT.read_text() + "# hand edit\n")
    r = run_script("--check", "--out", str(out))
    assert r.returncode == 1
    assert "stale" in r.stderr


def test_check_fails_when_the_output_is_missing(tmp_path):
    r = run_script("--check", "--out", str(tmp_path / "nope.py"))
    assert r.returncode == 1


def test_check_fails_when_a_preset_changed(tmp_path):
    raw = copy.deepcopy(REAL)
    raw["effects"]["fade-colors"] = "0x70"
    presets = write_preset(tmp_path / "presets", raw)
    r = run_script("--check", "--presets-dir", str(presets), "--out", str(OUT))
    assert r.returncode == 1


def test_generate_writes_then_check_passes(tmp_path):
    out = tmp_path / "presets_gen.py"
    r = run_script("--out", str(out))
    assert r.returncode == 0, r.stderr
    assert out.read_text() == OUT.read_text()
    assert run_script("--check", "--out", str(out)).returncode == 0


def test_generate_leaves_an_up_to_date_file_untouched(tmp_path):
    out = tmp_path / "presets_gen.py"
    out.write_text(OUT.read_text())
    mtime = out.stat().st_mtime_ns
    assert load_gen().main(["--out", str(out)]) == 0
    assert out.stat().st_mtime_ns == mtime
