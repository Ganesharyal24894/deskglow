"""Load scripts/gen_presets.py (a standalone script, not a package) for tests."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "gen_presets.py"
PRESETS_DIR = ROOT / "presets" / "controllers"
REAL = json.loads((PRESETS_DIR / "elk-bledom.json").read_text())


def load_gen():
    name = "deskglow_gen_presets_under_test"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def run_script(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=60)


def write_preset(directory, raw, stem="elk-bledom"):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.json").write_text(json.dumps(raw))
    return directory
