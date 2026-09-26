"""Hatch build hook: regenerate deskglow/model/presets_gen.py before building.

The generated module is checked in (so a plain checkout runs without building),
but a wheel must never ship tables that disagree with presets/controllers/*.json.
"""
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class PresetsBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        script = Path(self.root) / "scripts" / "gen_presets.py"
        if not script.exists():      # building from a wheel-only tree: nothing to do
            return
        subprocess.run([sys.executable, str(script)], cwd=self.root, check=True)
