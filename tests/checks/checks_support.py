"""Shared helpers for the scripts/ checker tests (imported by conftest and tests).

The checkers are standalone scripts, not a package, so they are loaded from
their file path. Fake packages are built in tmp_path with their own layers.json.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"

FAKE_LAYERS = {
    "package": "fakepkg",
    "layers": {
        "low": {
            "paths": ["fakepkg/low"],
            "internal": ["low"],
            "modules": ["__future__", "json", "typing"],
        },
        "special": {
            "paths": ["fakepkg/low/special"],
            "internal": ["low", "special"],
            "modules": ["os"],
        },
        "high": {
            "paths": ["fakepkg/high"],
            "internal": ["low", "high"],
            "modules": ["json", "importlib"],
        },
        "app": {
            "paths": ["fakepkg/app", "fakepkg/__init__.py"],
            "internal": ["low", "special", "high", "app"],
            "modules": ["importlib", "os"],
        },
    },
}


def load_script(name: str):
    """Import scripts/<name>.py as a fresh module."""
    mod_name = f"_script_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def write_tree(root: Path, files: dict) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
