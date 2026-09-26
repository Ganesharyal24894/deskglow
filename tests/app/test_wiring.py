"""deskglow.app.wiring: driver selection per platform (sys.platform + session).

Every builder is exercised on every host OS: per-user paths are pinned into
tmp_path through `home` / a fake platformdirs object."""
import json
import os
import sys
import types

import pytest

from deskglow.app import wiring
from deskglow.drivers import audio_soundcard, ble_bleak, screen_platform
from deskglow.drivers.focus_other import NoFocusTracker, QuartzFocusTracker, Win32FocusTracker
from deskglow.drivers.focus_x11 import XlibFocusTracker
from deskglow.drivers.hotkey_pynput import NoHotkey, PynputHotkey
from deskglow.drivers.ipc_tcp import TcpIpcClient, TcpIpcServer
from deskglow.drivers.ipc_unix import UnixIpcClient, UnixIpcServer
from deskglow.drivers.launchd import LaunchdAutostart
from deskglow.drivers.location_tz import TzLocation
from deskglow.drivers.process import PosixProcessControl, WindowsProcessControl
from deskglow.drivers.screen_mss import MssScreenSource
from deskglow.drivers.screen_wayland import WaylandScreenSource
from deskglow.drivers.storage_files import JsonFileStorage
from deskglow.drivers.storage_linux import LinuxStorage
from deskglow.drivers.systemd import SystemdAutostart
from deskglow.drivers.win_autostart import WindowsRunAutostart
from deskglow.model.presets import get_preset
from deskglow.view.strip import StripEncoder

X11 = {"DISPLAY": ":0", "XDG_SESSION_TYPE": "x11"}


@pytest.fixture
def dirs(tmp_path):
    base = tmp_path / "pd"
    return types.SimpleNamespace(user_config_dir=str(base / "cfg"), user_log_dir=str(base / "log"),
                                 user_data_dir=str(base / "data"),
                                 user_runtime_dir=str(base / "rt"))


def linux(tmp_path, **env):
    return wiring.build_services(platform="linux", home=str(tmp_path / "home"),
                                 env={"XDG_RUNTIME_DIR": str(tmp_path / "run"), **env})


def assert_common(s):
    assert isinstance(s.encoder, StripEncoder)
    assert s.preset == get_preset()
    assert isinstance(s.link, ble_bleak.BleakLink)
    assert s.link.write_uuid == get_preset().write_uuid
    assert isinstance(s.scanner, ble_bleak.BleakAdvertScanner)
    assert isinstance(s.location, TzLocation)


def test_linux_x11_picks_the_x11_drivers(tmp_path):
    s = linux(tmp_path, **X11)
    assert_common(s)
    assert isinstance(s.storage, LinuxStorage)
    assert isinstance(s.ipc_server, UnixIpcServer) and isinstance(s.ipc_client, UnixIpcClient)
    assert isinstance(s.autostart, SystemdAutostart)
    assert isinstance(s.process, PosixProcessControl)
    assert s.screen is MssScreenSource
    assert s.focus is XlibFocusTracker
    assert s.hotkey is PynputHotkey
    assert s.audio is audio_soundcard.linux_audio_source
    assert s.link._admin.__name__.endswith("bluez"), "Linux keeps BlueZ housekeeping"


def test_linux_wayland_picks_the_portal_and_no_focus_or_hotkey(tmp_path):
    s = linux(tmp_path, WAYLAND_DISPLAY="wayland-0", DISPLAY=":0")
    screen = s.screen()
    assert isinstance(screen, WaylandScreenSource)
    assert screen._storage is s.storage, "restore token must persist in the config"
    assert s.focus is NoFocusTracker
    assert s.hotkey is NoHotkey


def test_linux_socket_lives_in_the_runtime_dir(tmp_path):
    s = linux(tmp_path, **X11)
    expected = str(tmp_path / "run" / "deskglowd.sock")
    assert s.ipc_server.path == expected and s.ipc_client.path == expected


def test_linux_storage_uses_home_and_env(tmp_path):
    s = linux(tmp_path, DESKGLOW_ADDRESS="AA:BB:CC:DD:EE:FF", **X11)
    assert s.storage.config_dir() == str(tmp_path / "home" / ".config" / "deskglow")
    assert s.storage.address_override() == "AA:BB:CC:DD:EE:FF"
    assert s.process._log_path == s.storage.log_path()


def test_linux_wiring_runs_the_legacy_migration(tmp_path):
    legacy = tmp_path / "home" / ".config" / "sc295"
    legacy.mkdir(parents=True)
    (legacy / "config.json").write_text(json.dumps({"address": "11:22:33:44:55:66"}))
    assert linux(tmp_path, **X11).storage.load_config() == {"address": "11:22:33:44:55:66"}


@pytest.mark.parametrize("platform", ["linux", "linux2"])
def test_explicit_linux_platform_strings(platform, tmp_path):
    s = wiring.build_services(platform=platform, env=X11, home=str(tmp_path))
    assert isinstance(s.storage, LinuxStorage)


def test_macos_picks_the_macos_drivers(tmp_path, dirs):
    s = wiring.build_services(platform="darwin", env={}, home=str(tmp_path / "h"), dirs=dirs)
    assert_common(s)
    assert isinstance(s.storage, JsonFileStorage)
    assert s.storage.config_dir() == dirs.user_config_dir
    assert s.storage.log_path() == os.path.join(dirs.user_log_dir, "daemon.log")
    assert isinstance(s.ipc_server, UnixIpcServer)
    assert s.ipc_server.path == s.ipc_client.path == os.path.join(dirs.user_runtime_dir,
                                                                  "deskglowd.sock")
    assert os.path.isdir(dirs.user_runtime_dir)
    assert isinstance(s.autostart, LaunchdAutostart)
    assert s.autostart.path.startswith(str(tmp_path / "h" / "Library" / "LaunchAgents"))
    assert isinstance(s.process, PosixProcessControl)
    assert s.screen is screen_platform.macos_screen
    assert s.focus is QuartzFocusTracker
    assert s.audio is audio_soundcard.SoundcardAudioSource
    assert s.hotkey is PynputHotkey
    assert isinstance(s.link._admin, ble_bleak.NoAdapterAdmin)
    s.storage.save_config({"address": "UUID", "name": "ELK-BLEDOM"})
    assert s.link._saved_name() == "ELK-BLEDOM", "macOS falls back to the saved name"


def test_windows_picks_the_windows_drivers(tmp_path, dirs):
    s = wiring.build_services(platform="win32", env={}, dirs=dirs)
    assert_common(s)
    assert isinstance(s.storage, JsonFileStorage)
    assert s.storage.config_dir() == dirs.user_config_dir
    assert isinstance(s.ipc_server, TcpIpcServer) and isinstance(s.ipc_client, TcpIpcClient)
    assert s.ipc_server.endpoint_file == s.ipc_client.endpoint_file == os.path.join(
        dirs.user_data_dir, "deskglowd.json")
    assert isinstance(s.autostart, WindowsRunAutostart)
    assert isinstance(s.process, WindowsProcessControl)
    assert s.process._log_path == os.path.join(dirs.user_log_dir, "daemon.log")
    assert s.screen is screen_platform.windows_screen
    assert s.focus is Win32FocusTracker
    assert s.audio is audio_soundcard.SoundcardAudioSource
    assert s.hotkey is PynputHotkey
    assert isinstance(s.link._admin, ble_bleak.NoAdapterAdmin)


@pytest.mark.parametrize("platform", ["cygwin", "freebsd14", "aix"])
def test_other_platforms_are_unsupported(monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    with pytest.raises(wiring.UnsupportedPlatform, match=platform) as exc:
        wiring.build_services()
    assert isinstance(exc.value, RuntimeError), "the CLI reports RuntimeErrors cleanly"


def test_explicit_platform_argument_wins_over_sys_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(wiring.UnsupportedPlatform, match="sunos"):
        wiring.build_services(platform="sunos5")
