"""Fixtures for the scripts/ checker tests."""
from __future__ import annotations

import json

import pytest
from checks_support import FAKE_LAYERS, load_script, write_tree


@pytest.fixture(scope="session")
def layers_mod():
    return load_script("check_layers")


@pytest.fixture(scope="session")
def lines_mod():
    return load_script("check_lines")


@pytest.fixture(scope="session")
def check_mod():
    return load_script("check")


@pytest.fixture
def fake_repo(tmp_path):
    """Return build(files, config=FAKE_LAYERS) -> (root, config_path)."""
    base = {
        "fakepkg/__init__.py": "__version__ = '1.0'\n",
        "fakepkg/low/__init__.py": "",
        "fakepkg/low/special/__init__.py": "",
        "fakepkg/high/__init__.py": "",
        "fakepkg/app/__init__.py": "",
    }

    def build(files: dict, config: dict | None = None):
        write_tree(tmp_path, {**base, **files})
        cfg_path = tmp_path / "layers.json"
        cfg_path.write_text(json.dumps(FAKE_LAYERS if config is None else config),
                            encoding="utf-8")
        return tmp_path, cfg_path

    return build
