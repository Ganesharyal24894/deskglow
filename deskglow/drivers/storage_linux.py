"""Storage on Linux: JSON files under ~/.config/deskglow, written atomically.

Also migrates the files of the project's former name (~/.config/sc295) on
first run, so an upgrade keeps the configured strip and last mode.
"""
import os
import shutil

from . import paths
from .storage_files import ADDRESS_ENV, JsonFileStorage

__all__ = ["ADDRESS_ENV", "LinuxStorage"]

LEGACY_DIR_NAME = "sc295"          # the project's name before it became Deskglow
MIGRATED_FILES = ("config.json", "state.json")


class LinuxStorage(JsonFileStorage):
    """`home` pins the directory to <home>/.config/deskglow (tests, wiring);
    without it platformdirs decides (~/.config/deskglow, or $XDG_CONFIG_HOME)."""

    def __init__(self, home=None, env=None, dirs=None):
        if home is not None:
            directory = os.path.join(home, ".config", paths.APP)
        else:
            directory = (dirs or paths.dirs_for("linux")).user_config_dir
        super().__init__(directory, env=env)

    def migrate_legacy(self):
        """Copy config/state from ~/.config/sc295 if the new dir doesn't exist yet.

        Returns the names of the files copied (empty if nothing to do). The old
        directory is left in place, untouched."""
        legacy = os.path.join(os.path.dirname(self._dir), LEGACY_DIR_NAME)
        if os.path.exists(self._dir) or not os.path.isdir(legacy):
            return []
        os.makedirs(self._dir, exist_ok=True)
        copied = []
        for name in MIGRATED_FILES:
            src = os.path.join(legacy, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(self._dir, name))
                copied.append(name)
        return copied
