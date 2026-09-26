"""check_layers.py: layers.json validation and the command-line entry point."""
from __future__ import annotations

import copy
import subprocess
import sys

import pytest
from checks_support import FAKE_LAYERS, SCRIPTS_DIR


def broken(mutate):
    cfg = copy.deepcopy(FAKE_LAYERS)
    mutate(cfg)
    return cfg


BAD_CONFIGS = {
    "missing_package": (broken(lambda c: c.pop("package")), "'package'"),
    "missing_layers": (broken(lambda c: c.pop("layers")), "'layers'"),
    "empty_layers": (broken(lambda c: c.update(layers={})), "'layers'"),
    "layers_not_object": (broken(lambda c: c.update(layers=[])), "'layers'"),
    "layer_not_object": (broken(lambda c: c["layers"].update(low=[])),
                         "layer 'low' must be an object"),
    "missing_modules": (broken(lambda c: c["layers"]["low"].pop("modules")),
                        "layer 'low' missing or invalid key 'modules'"),
    "missing_internal": (broken(lambda c: c["layers"]["high"].pop("internal")),
                         "layer 'high' missing or invalid key 'internal'"),
    "missing_paths": (broken(lambda c: c["layers"]["app"].pop("paths")),
                      "layer 'app' missing or invalid key 'paths'"),
    "modules_not_strings": (broken(lambda c: c["layers"]["low"].update(modules=[1])),
                            "layer 'low' missing or invalid key 'modules'"),
    "unknown_internal": (broken(lambda c: c["layers"]["high"]["internal"].append("ghost")),
                         "layer 'high' lists unknown internal layer(s): ghost"),
}


@pytest.mark.parametrize("case", sorted(BAD_CONFIGS))
def test_bad_config_gives_clean_error(layers_mod, fake_repo, capsys, case):
    cfg, fragment = BAD_CONFIGS[case]
    root, cfg_path = fake_repo({}, config=cfg)
    code = layers_mod.run(root, cfg_path)
    out = capsys.readouterr().out
    assert code == 2
    assert out.startswith("check_layers: config error:"), out
    assert fragment in out
    assert "Traceback" not in out


def test_invalid_json(layers_mod, fake_repo, capsys):
    root, cfg_path = fake_repo({})
    cfg_path.write_text("{ not json", encoding="utf-8")
    assert layers_mod.run(root, cfg_path) == 2
    assert "config error" in capsys.readouterr().out


def test_missing_config_file(layers_mod, tmp_path, capsys):
    assert layers_mod.run(tmp_path, tmp_path / "nope.json") == 2
    assert "config error" in capsys.readouterr().out


def test_missing_package_dir(layers_mod, fake_repo, capsys):
    root, cfg_path = fake_repo({}, config=broken(lambda c: c.update(package="other")))
    assert layers_mod.run(root, cfg_path) == 2
    assert "package directory 'other/' not found" in capsys.readouterr().out


def test_real_layers_json_is_valid(layers_mod):
    cfg = layers_mod.load_config(SCRIPTS_DIR / "layers.json")
    assert cfg["package"] == "deskglow"
    assert "app" in cfg["layers"]


def cli(root, cfg_path):
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "check_layers.py"),
         "--root", str(root), "--config", str(cfg_path)],
        capture_output=True, text=True, timeout=60,
    )


def test_cli_ok_and_failure_exit_codes(fake_repo):
    root, cfg_path = fake_repo({"fakepkg/low/a.py": "import json\n"})
    ok = cli(root, cfg_path)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "check_layers: OK" in ok.stdout
    (root / "fakepkg/low/b.py").write_text("import requests\n", encoding="utf-8")
    bad = cli(root, cfg_path)
    assert bad.returncode == 1
    assert "fakepkg/low/b.py:1: [low] imports 'requests' (not allowed)" in bad.stdout
