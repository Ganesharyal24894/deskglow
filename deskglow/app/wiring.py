"""Pick driver implementations for this platform and bundle them as Services.

Porting to a new OS means adding driver modules and one builder here; model,
services, controller and view code do not change. Each builder imports its
drivers lazily, so building for one OS never loads another OS's modules and a
core install (no screen/audio extras) still works.
"""
import os
import sys

from ..model.presets import get_preset
from ..services.container import Services
from ..view.strip import StripEncoder


class UnsupportedPlatform(RuntimeError):
    """No driver set exists for this OS yet."""


def _saved_name(storage):
    return lambda: storage.load_config().get("name")


def _linux(env, home, dirs):
    from ..drivers import audio_soundcard, ble_bleak, ipc_unix, session_linux
    from ..drivers.location_tz import TzLocation
    from ..drivers.process import PosixProcessControl
    from ..drivers.storage_linux import LinuxStorage
    from ..drivers.systemd import SystemdAutostart
    preset = get_preset()
    storage = LinuxStorage(home=home, env=env, dirs=dirs)
    storage.migrate_legacy()
    sock = ipc_unix.default_socket_path(env)
    if session_linux.is_wayland(env):
        from ..drivers.focus_other import NoFocusTracker
        from ..drivers.hotkey_pynput import NoHotkey
        from ..drivers.screen_wayland import WaylandScreenSource

        def screen():
            return WaylandScreenSource(storage)
        focus, hotkey = NoFocusTracker, NoHotkey
    else:
        from ..drivers.focus_x11 import XlibFocusTracker
        from ..drivers.hotkey_pynput import PynputHotkey
        from ..drivers.screen_mss import MssScreenSource
        screen, focus, hotkey = MssScreenSource, XlibFocusTracker, PynputHotkey
    return Services(
        preset=preset,
        encoder=StripEncoder(preset),
        storage=storage,
        link=ble_bleak.BleakLink(preset.write_uuid),
        scanner=ble_bleak.BleakAdvertScanner(),
        ipc_server=ipc_unix.UnixIpcServer(sock),
        ipc_client=ipc_unix.UnixIpcClient(sock),
        autostart=SystemdAutostart(),
        process=PosixProcessControl(storage.log_path()),
        screen=screen,
        focus=focus,
        audio=audio_soundcard.linux_audio_source,
        hotkey=hotkey,
        location=TzLocation(),
    )


def _darwin(env, home, dirs):
    from ..drivers import ble_bleak, ipc_unix, paths, screen_platform
    from ..drivers.audio_soundcard import SoundcardAudioSource
    from ..drivers.focus_other import QuartzFocusTracker
    from ..drivers.hotkey_pynput import PynputHotkey
    from ..drivers.launchd import LaunchdAutostart
    from ..drivers.location_tz import TzLocation
    from ..drivers.process import PosixProcessControl
    from ..drivers.storage_files import JsonFileStorage
    dirs = dirs or paths.dirs_for("darwin")
    preset = get_preset()
    storage = JsonFileStorage(dirs.user_config_dir,
                              os.path.join(dirs.user_log_dir, "daemon.log"), env)
    sock = ipc_unix.macos_socket_path(dirs)
    agents = os.path.join(home, "Library", "LaunchAgents") if home else None
    return Services(
        preset=preset,
        encoder=StripEncoder(preset),
        storage=storage,
        link=ble_bleak.BleakLink(preset.write_uuid, admin=ble_bleak.NoAdapterAdmin(),
                                 saved_name=_saved_name(storage)),
        scanner=ble_bleak.BleakAdvertScanner(),
        ipc_server=ipc_unix.UnixIpcServer(sock),
        ipc_client=ipc_unix.UnixIpcClient(sock),
        autostart=LaunchdAutostart(dirs.user_log_dir, agents_dir=agents),
        process=PosixProcessControl(storage.log_path()),
        screen=screen_platform.macos_screen,
        focus=QuartzFocusTracker,
        audio=SoundcardAudioSource,
        hotkey=PynputHotkey,
        location=TzLocation(),
    )


def _win32(env, home, dirs):
    from ..drivers import ble_bleak, ipc_tcp, paths, screen_platform
    from ..drivers.audio_soundcard import SoundcardAudioSource
    from ..drivers.focus_other import Win32FocusTracker
    from ..drivers.hotkey_pynput import PynputHotkey
    from ..drivers.location_tz import TzLocation
    from ..drivers.process import WindowsProcessControl
    from ..drivers.storage_files import JsonFileStorage
    from ..drivers.win_autostart import WindowsRunAutostart
    dirs = dirs or paths.dirs_for("win32")
    preset = get_preset()
    storage = JsonFileStorage(dirs.user_config_dir,
                              os.path.join(dirs.user_log_dir, "daemon.log"), env)
    endpoint = ipc_tcp.default_endpoint_path(dirs)
    return Services(
        preset=preset,
        encoder=StripEncoder(preset),
        storage=storage,
        link=ble_bleak.BleakLink(preset.write_uuid, admin=ble_bleak.NoAdapterAdmin()),
        scanner=ble_bleak.BleakAdvertScanner(),
        ipc_server=ipc_tcp.TcpIpcServer(endpoint),
        ipc_client=ipc_tcp.TcpIpcClient(endpoint),
        autostart=WindowsRunAutostart(),
        process=WindowsProcessControl(storage.log_path()),
        screen=screen_platform.windows_screen,
        focus=Win32FocusTracker,
        audio=SoundcardAudioSource,
        hotkey=PynputHotkey,
        location=TzLocation(),
    )


# sys.platform prefix -> builder(env, home, dirs)
BUILDERS = {"linux": _linux, "darwin": _darwin, "win32": _win32}


def build_services(platform=None, env=None, home=None, dirs=None):
    """Services for `platform` (default: this machine), or UnsupportedPlatform.

    `home` and `dirs` (a platformdirs-like object) pin the per-user paths;
    tests use them to build any OS's services in a temp dir."""
    platform = sys.platform if platform is None else platform
    env = os.environ if env is None else env
    for prefix, builder in BUILDERS.items():
        if platform.startswith(prefix):
            return builder(env, home, dirs)
    raise UnsupportedPlatform(
        f"Deskglow has no drivers for {platform!r} yet (supported: {', '.join(BUILDERS)})")
