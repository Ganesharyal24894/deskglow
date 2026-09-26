"""Packaging-level contracts that must hold for a public release."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE_ONLY = {"numpy", "mss", "Xlib", "soundcard", "pynput", "Quartz"}   # optional extras


def _import_without_extras(module):
    """Import `module` in a subprocess where the optional extras are missing."""
    code = f"""
import builtins
BLOCK = {sorted(CORE_ONLY)!r}
_real = builtins.__import__
def guard(name, *a, **k):
    if name.split('.')[0] in BLOCK:
        raise ImportError("No module named " + repr(name))
    return _real(name, *a, **k)
builtins.__import__ = guard
import {module}
print("ok")
"""
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("module", ["deskglow.app.cli", "deskglow.app.daemon",
                                    "deskglow.app.wiring", "deskglow.controller.modes"])
def test_core_install_imports_without_optional_extras(module):
    """A plain `pip install deskglow` (no screen/audio extras) must still work."""
    r = _import_without_extras(module)
    assert r.returncode == 0, (
        f"{module} cannot be imported without the optional extras:\n{r.stderr}")


def test_cli_reports_its_version(capsys):
    """`deskglow --version` is table stakes for a published CLI."""
    from deskglow import __version__
    from deskglow.view.cli_parser import build_parser
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_package_version_is_importable_and_sane():
    """hatchling reads the version out of deskglow/__init__.py; keep it parseable."""
    from deskglow import __version__
    assert re.match(r"^\d+\.\d+\.\d+", __version__), __version__


def test_pyproject_declares_the_console_scripts():
    tomllib = pytest.importorskip("tomllib")
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text())
    scripts = meta["project"]["scripts"]
    assert scripts["deskglow"] == "deskglow.app.cli:main"
    assert scripts["deskglowd"] == "deskglow.app.daemon:main"


def test_python_dash_m_deskglow_runs_the_cli():
    r = subprocess.run([sys.executable, "-m", "deskglow", "--version"], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("deskglow ")
