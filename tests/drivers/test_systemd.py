"""drivers.systemd: the deskglowd user unit (start / is_enabled / set_enabled)
and the XDG-autostart fallback. systemctl is never run for real."""
import subprocess
import types

import pytest

from deskglow.drivers import systemd
from deskglow.drivers.xdg_autostart import XdgAutostart


class Systemctl:
    """Fake subprocess.run for `systemctl --user ...`: rc per sub-command."""

    def __init__(self, rc=None, exc=None, stderr=b""):
        self.rc = rc or {}
        self.exc = exc
        self.stderr = stderr
        self.calls = []

    def __call__(self, cmd, **kw):
        assert cmd[:2] == ["systemctl", "--user"] and kw.get("timeout")
        self.calls.append(cmd[2:])
        if self.exc is not None:
            raise self.exc
        return types.SimpleNamespace(returncode=self.rc.get(cmd[2], 0), stderr=self.stderr)


def make(tmp_path, **kw):
    run = Systemctl(**kw)
    xdg = XdgAutostart(autostart_dir=str(tmp_path / "autostart"), executable="/py")
    auto = systemd.SystemdAutostart(run=run, unit_dir=str(tmp_path / "units"), xdg=xdg,
                                    executable="/venv/bin/python")
    return auto, run, xdg


def test_start_starts_the_deskglowd_user_unit(tmp_path):
    auto, run, _ = make(tmp_path)
    assert auto.start() is True
    assert run.calls == [["start", "deskglowd.service"]]


def test_start_reports_a_failed_start(tmp_path):
    assert make(tmp_path, rc={"start": 5})[0].start() is False


@pytest.mark.parametrize("exc", [FileNotFoundError("systemctl"),
                                 subprocess.TimeoutExpired("systemctl", 8)])
def test_start_treats_errors_as_not_started(tmp_path, exc):
    assert make(tmp_path, exc=exc)[0].start() is False


def test_enable_writes_the_unit_reloads_and_enables(tmp_path):
    auto, run, _ = make(tmp_path)
    auto.set_enabled(True)
    text = (tmp_path / "units" / "deskglowd.service").read_text()
    assert "ExecStart=/venv/bin/python -m deskglow.app.daemon\n" in text
    assert "Restart=always" in text
    assert "PartOf=graphical-session.target" in text
    assert "WantedBy=graphical-session.target" in text
    assert run.calls == [["show-environment"], ["daemon-reload"],
                         ["enable", "deskglowd.service"]]


def test_enable_keeps_an_existing_unit_file(tmp_path):
    auto, _run, _ = make(tmp_path)
    (tmp_path / "units").mkdir()
    (tmp_path / "units" / "deskglowd.service").write_text("mine")
    auto.set_enabled(True)
    assert (tmp_path / "units" / "deskglowd.service").read_text() == "mine"


def test_exec_start_quotes_an_interpreter_path_with_spaces():
    assert 'ExecStart="/my venv/python" -m deskglow.app.daemon' in \
        systemd.unit_text("/my venv/python")
    assert "ExecStart=/usr/bin/python3 -m deskglow.app.daemon\n" in \
        systemd.unit_text("/usr/bin/python3")


def test_a_refused_enable_raises_oserror_with_systemctls_reason(tmp_path):
    auto, _run, _ = make(tmp_path, rc={"enable": 1}, stderr=b"Access denied")
    with pytest.raises(OSError, match="Access denied"):
        auto.set_enabled(True)


def test_disable_disables_the_unit_and_removes_a_fallback_entry(tmp_path):
    auto, run, xdg = make(tmp_path)
    (tmp_path / "autostart").mkdir()
    (tmp_path / "autostart" / "deskglowd.desktop").write_text("x")
    auto.set_enabled(False)
    assert ["disable", "deskglowd.service"] in run.calls
    assert not xdg.is_enabled()


@pytest.mark.parametrize("rc,expected", [(0, True), (1, False)])
def test_is_enabled_asks_systemctl(tmp_path, rc, expected):
    auto, run, _ = make(tmp_path, rc={"is-enabled": rc})
    assert auto.is_enabled() is expected
    assert ["is-enabled", "deskglowd.service"] in run.calls


def test_without_systemd_user_it_falls_back_to_xdg_autostart(tmp_path):
    auto, run, xdg = make(tmp_path, rc={"show-environment": 1, "is-enabled": 1})
    auto.set_enabled(True)
    assert xdg.is_enabled() and auto.is_enabled()
    assert not (tmp_path / "units").exists(), "wrote a unit nobody will load"
    assert ["enable", "deskglowd.service"] not in run.calls
    auto.set_enabled(False)
    assert not auto.is_enabled()


def test_missing_systemctl_binary_also_falls_back(tmp_path):
    auto, _run, xdg = make(tmp_path, exc=FileNotFoundError("systemctl"))
    auto.set_enabled(True)
    assert xdg.is_enabled()
