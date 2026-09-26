"""drivers.paths (platformdirs per target OS) and drivers.storage_files."""
import os
import sys
import types

import pytest

from deskglow.drivers import paths
from deskglow.drivers.storage_files import JsonFileStorage


def fake_loader(seen):
    def cls(tag):
        def make(**kw):
            seen.append((tag, kw))
            return tag
        return make
    mods = {"unix": types.SimpleNamespace(Unix=cls("unix")),
            "macos": types.SimpleNamespace(MacOS=cls("macos")),
            "windows": types.SimpleNamespace(Windows=cls("windows")),
            None: types.SimpleNamespace(PlatformDirs=cls("auto"))}
    return mods.__getitem__


@pytest.mark.parametrize("platform,tag", [("linux", "unix"), ("darwin", "macos"),
                                          ("win32", "windows"), ("freebsd14", "auto")])
def test_dirs_follow_the_target_platform_not_the_host(platform, tag):
    seen = []
    assert paths.dirs_for(platform, loader=fake_loader(seen)) == tag
    assert seen == [(tag, {"appname": "deskglow", "appauthor": False, "roaming": False})]


def test_linux_dirs_are_the_classic_xdg_paths(monkeypatch, tmp_path):
    """Real platformdirs: Linux config must stay ~/.config/deskglow."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    d = paths.dirs_for("linux")
    assert os.path.normpath(d.user_config_dir) == \
        os.path.join(str(tmp_path), ".config", "deskglow")


@pytest.mark.skipif(sys.platform != "darwin", reason="platformdirs' macOS class reads "
                    "the real home; checked on macOS CI only")
def test_macos_dirs_live_in_library():
    d = paths.dirs_for("darwin")
    assert d.user_config_dir.endswith("Library/Application Support/deskglow")
    assert d.user_log_dir.endswith("Library/Logs/deskglow")


def test_private_dir_creates_owner_only_and_fixes_an_existing_mode(tmp_path):
    calls = []
    target = str(tmp_path / "rt")
    assert paths.private_dir(target, makedirs=lambda p, **kw: calls.append(("mk", p, kw)),
                             chmod=lambda p, m: calls.append(("chmod", p, m))) == target
    assert calls == [("mk", target, {"mode": 0o700, "exist_ok": True}),
                     ("chmod", target, 0o700)]


def test_json_file_storage_round_trips_and_uses_the_given_log(tmp_path):
    s = JsonFileStorage(str(tmp_path / "cfg"), str(tmp_path / "logs" / "d.log"),
                        env={"DESKGLOW_ADDRESS": "X"})
    assert s.load_config() == {} and s.load_state() is None
    s.save_config({"address": "A", "name": "ELK-BLEDOM"})
    s.save_state({"mode": "calm"})
    assert s.load_config() == {"address": "A", "name": "ELK-BLEDOM"}
    assert s.load_state() == {"mode": "calm"}
    assert s.log_path() == str(tmp_path / "logs" / "d.log")
    assert s.config_dir() == str(tmp_path / "cfg")
    assert s.address_override() == "X"


def test_json_file_storage_defaults_its_log_into_the_config_dir(tmp_path):
    s = JsonFileStorage(str(tmp_path), env={})
    assert s.log_path() == os.path.join(str(tmp_path), "daemon.log")
    assert s.address_override() is None
