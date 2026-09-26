"""Login entries: XDG .desktop (Linux fallback) and the macOS LaunchAgent.
launchctl is never run for real; every file lands in tmp_path."""
import plistlib
import types

import pytest

from deskglow.drivers import launchd
from deskglow.drivers.xdg_autostart import XdgAutostart, quote_argv


# ------------------------------------------------------------------ XDG ------

def test_xdg_entry_runs_the_daemon_module(tmp_path):
    xdg = XdgAutostart(autostart_dir=str(tmp_path), executable="/v/bin/python")
    assert not xdg.is_enabled()
    xdg.set_enabled(True)
    text = (tmp_path / "deskglowd.desktop").read_text()
    assert "Exec=/v/bin/python -m deskglow.app.daemon\n" in text
    assert text.startswith("[Desktop Entry]\nType=Application\n")
    assert xdg.is_enabled()
    xdg.set_enabled(False)
    assert not xdg.is_enabled()
    xdg.set_enabled(False)                      # already off: no error


def test_xdg_dir_honours_xdg_config_home(tmp_path):
    xdg = XdgAutostart(env={"XDG_CONFIG_HOME": str(tmp_path / "cfg")})
    assert xdg.path == str(tmp_path / "cfg" / "autostart" / "deskglowd.desktop")


def test_xdg_start_defers_to_the_client_spawn():
    assert XdgAutostart(autostart_dir="/unused").start() is False


def test_quote_argv_quotes_only_what_needs_it():
    assert quote_argv(["/a b/py", "-m", 'x"y']) == '"/a b/py" -m "x\\"y"'


# -------------------------------------------------------------- launchd ------

class Launchctl:
    def __init__(self, rc=None):
        self.rc = rc or {}
        self.calls = []

    def __call__(self, cmd, **kw):
        assert cmd[0] == "launchctl"
        self.calls.append(cmd[1:])
        return types.SimpleNamespace(returncode=self.rc.get(cmd[1], 0), stderr=b"denied")


def make_agent(tmp_path, **kw):
    run = Launchctl(**kw)
    agent = launchd.LaunchdAutostart(str(tmp_path / "logs"), agents_dir=str(tmp_path / "LA"),
                                     run=run, uid=501, executable="/py")
    return agent, run


def test_enable_writes_the_agent_plist_and_bootstraps_it(tmp_path):
    agent, run = make_agent(tmp_path)
    agent.set_enabled(True)
    with open(tmp_path / "LA" / "io.deskglow.daemon.plist", "rb") as f:
        plist = plistlib.load(f)
    assert plist["Label"] == "io.deskglow.daemon"
    assert plist["ProgramArguments"] == ["/py", "-m", "deskglow.app.daemon"]
    assert plist["RunAtLoad"] is True
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist["LimitLoadToSessionType"] == "Aqua"
    log = str(tmp_path / "logs" / "daemon.log")
    assert plist["StandardOutPath"] == plist["StandardErrorPath"] == log
    assert run.calls[-1] == ["bootstrap", "gui/501", agent.path]
    assert agent.is_enabled()


def test_a_refused_bootstrap_raises_oserror(tmp_path):
    agent, _ = make_agent(tmp_path, rc={"bootstrap": 5})
    with pytest.raises(OSError, match="launchctl bootstrap failed: denied"):
        agent.set_enabled(True)


def test_disable_boots_out_and_removes_the_plist(tmp_path):
    agent, run = make_agent(tmp_path)
    agent.set_enabled(True)
    agent.set_enabled(False)
    assert ["bootout", "gui/501/io.deskglow.daemon"] in run.calls
    assert not agent.is_enabled()


def test_start_kickstarts_an_installed_agent(tmp_path):
    agent, run = make_agent(tmp_path)
    assert agent.start() is False, "nothing installed yet"
    agent.set_enabled(True)
    run.calls.clear()
    assert agent.start() is True
    assert run.calls == [["kickstart", "gui/501/io.deskglow.daemon"]]


def test_start_bootstraps_when_the_agent_is_not_loaded(tmp_path):
    agent, run = make_agent(tmp_path)
    agent.set_enabled(True)
    run.rc["kickstart"] = 113
    run.calls.clear()
    assert agent.start() is True
    assert run.calls[-1] == ["bootstrap", "gui/501", agent.path]
