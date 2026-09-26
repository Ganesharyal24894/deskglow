"""Per-user directories on every OS, via `platformdirs` (app name "deskglow").

Linux:   ~/.config/deskglow (config + log), $XDG_RUNTIME_DIR (socket)
macOS:   ~/Library/Application Support/deskglow, ~/Library/Logs/deskglow,
         ~/Library/Caches/TemporaryItems/deskglow (socket, 0700)
Windows: %LOCALAPPDATA%\\deskglow (config, IPC endpoint file), ...\\Logs

The platformdirs class is picked from the *target* platform string rather than
the running OS, so wiring for one OS can be exercised on another in tests.
"""
import os
import sys

APP = "deskglow"
_CLASSES = {"linux": ("unix", "Unix"), "darwin": ("macos", "MacOS"),
            "win32": ("windows", "Windows")}


def _load(submodule):
    import platformdirs
    import platformdirs.macos
    import platformdirs.unix
    import platformdirs.windows
    return getattr(platformdirs, submodule) if submodule else platformdirs


def dirs_for(platform=None, loader=_load):
    """A platformdirs object for `platform` (default: this machine). Its
    user_*_dir attributes are plain strings; nothing is created."""
    platform = sys.platform if platform is None else platform
    for prefix, (module, cls) in _CLASSES.items():
        if platform.startswith(prefix):
            return getattr(loader(module), cls)(appname=APP, appauthor=False, roaming=False)
    return loader(None).PlatformDirs(appname=APP, appauthor=False, roaming=False)


def private_dir(path, makedirs=os.makedirs, chmod=os.chmod):
    """Create `path` owner-only (0700) and return it. chmod runs even if it
    existed, because makedirs(exist_ok=True) leaves an old mode alone."""
    makedirs(path, mode=0o700, exist_ok=True)
    chmod(path, 0o700)
    return path
