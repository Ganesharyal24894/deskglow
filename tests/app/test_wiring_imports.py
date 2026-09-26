"""Building one OS's services must not load another OS's (or optional) modules."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HEAVY = ["Quartz", "AppKit", "soundcard", "pynput", "dbus_fast", "mss", "numpy", "Xlib",
         "tzlocal", "PySide6"]

CODE = """
import sys, types, tempfile, os
from deskglow.app import wiring
d = tempfile.mkdtemp()
dirs = types.SimpleNamespace(**{k: os.path.join(d, k) for k in (
    "user_config_dir", "user_log_dir", "user_data_dir", "user_runtime_dir")})
wiring.build_services(platform=%r, env={"DISPLAY": ":0"}, home=d, dirs=dirs)
print(",".join(sorted(m for m in %r if m in sys.modules)))
print("winreg" in sys.modules)
"""


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32"])
def test_building_services_loads_no_heavy_or_foreign_modules(platform):
    r = subprocess.run([sys.executable, "-c", CODE % (platform, HEAVY)], cwd=ROOT,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    loaded, winreg = r.stdout.split("\n")[:2]
    assert loaded == "", f"building {platform} services imported {loaded}"
    if sys.platform != "win32":
        assert winreg == "False", "winreg imported on a non-Windows host"
