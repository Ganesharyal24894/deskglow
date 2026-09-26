"""x11_display.ensure_display_env: recovering DISPLAY/XAUTHORITY for a service."""
import os
import subprocess

import pytest
from x11_support import fake_run

from deskglow.drivers import x11_display


@pytest.fixture
def clean_display_env():
    """Save/restore DISPLAY and XAUTHORITY: ensure_display_env writes to os.environ."""
    saved = {k: os.environ.get(k) for k in ("DISPLAY", "XAUTHORITY")}
    for k in saved:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def display_set(clean_display_env):
    """A session that already has DISPLAY/XAUTHORITY, so no systemctl lookup."""
    os.environ["DISPLAY"] = ":0"
    os.environ["XAUTHORITY"] = "/run/user/1000/gdm/Xauthority"


# --------------------------------------------------- ensure_display_env -----

def test_ensure_display_env_defaults_display(monkeypatch, clean_display_env):
    """With nothing available at all, DISPLAY still ends up as ':0'."""
    fake_run(monkeypatch, systemctl="")
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":0"


def test_ensure_display_env_pulls_from_systemctl(monkeypatch, clean_display_env):
    """A systemd --user daemon inherits DISPLAY/XAUTHORITY from the user manager."""
    fake_run(monkeypatch, systemctl=(
        "LANG=en_GB.UTF-8\n"
        "DISPLAY=:1\n"
        "XAUTHORITY=/run/user/1000/gdm/Xauthority\n"
        "PATH=/usr/bin\n"
    ))
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":1"
    assert os.environ["XAUTHORITY"] == "/run/user/1000/gdm/Xauthority"


def test_ensure_display_env_fills_only_the_missing_variable(monkeypatch, clean_display_env):
    """An already-exported DISPLAY is never overwritten by the systemctl value."""
    os.environ["DISPLAY"] = ":9"
    fake_run(monkeypatch, systemctl="DISPLAY=:1\nXAUTHORITY=/tmp/xauth\n")
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":9"
    assert os.environ["XAUTHORITY"] == "/tmp/xauth"


def test_ensure_display_env_skips_systemctl_when_nothing_is_missing(
        monkeypatch, display_set):
    """No lookup at all when both variables are already exported."""
    calls = []
    fake_run(monkeypatch, systemctl="DISPLAY=:5\n", calls=calls)
    x11_display.ensure_display_env()
    assert calls == []
    assert os.environ["DISPLAY"] == ":0"


def test_ensure_display_env_survives_systemctl_failure(monkeypatch, clean_display_env):
    """systemctl missing/timing out must not take the daemon down."""
    fake_run(monkeypatch, raises=subprocess.TimeoutExpired("systemctl", 5))
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":0"


def test_ensure_display_env_survives_missing_systemctl(monkeypatch, clean_display_env):
    """Non-systemd systems have no `systemctl` at all."""
    fake_run(monkeypatch, raises=FileNotFoundError("systemctl"))
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":0"
    assert "XAUTHORITY" not in os.environ


def test_ensure_display_env_ignores_junk_output(monkeypatch, clean_display_env):
    """Lines without '=' are skipped rather than crashing the split."""
    fake_run(monkeypatch, systemctl="no equals sign here\n\nDISPLAY=:2\n")
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":2"


def test_ensure_display_env_ignores_empty_values(monkeypatch, clean_display_env):
    """An empty DISPLAY= from systemctl is not a usable display."""
    fake_run(monkeypatch, systemctl="DISPLAY=\nXAUTHORITY=\n")
    x11_display.ensure_display_env()
    assert os.environ["DISPLAY"] == ":0"
    assert "XAUTHORITY" not in os.environ


def test_ensure_display_env_keeps_values_containing_equals(monkeypatch, clean_display_env):
    """split('=', 1) keeps '=' inside a value intact."""
    fake_run(monkeypatch, systemctl="XAUTHORITY=/tmp/xa=uth\nDISPLAY=:3\n")
    x11_display.ensure_display_env()
    assert os.environ["XAUTHORITY"] == "/tmp/xa=uth"
