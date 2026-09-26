"""deskglow.view.cli: main() dispatch, Cli.send() and the human-readable output.

No daemon, process or radio is ever touched: services are fakes from
tests/fakes.py and the daemon's replies are scripted.
"""
import pytest
from fakes import FakeIpcClient, make_services

from deskglow.view import cli


@pytest.fixture
def sent(monkeypatch):
    """Capture the requests main() would send, without touching a daemon."""
    seen = []

    async def fake_send(self, req):
        seen.append(req)
        return 0

    async def already_running(self):
        return True

    monkeypatch.setattr(cli.Cli, "send", fake_send)
    # restart-daemon also makes sure a daemon is up again afterwards
    monkeypatch.setattr(cli.DaemonClient, "ensure_daemon", already_running)
    return seen


def run_main(argv, services):
    return cli.main(argv, services_factory=lambda: services)


# ------------------------------------------------------------------ main() ---

def test_patterns_lists_effects_without_building_services(capsys):
    """`deskglow patterns` is pure local information: it never needs services."""
    def boom():
        raise AssertionError("patterns built services")

    assert cli.main(["patterns"], services_factory=boom) == 0
    out = capsys.readouterr().out
    assert "fade-colors" in out and "blink-white" in out


def test_help_never_builds_services():
    def boom():
        raise AssertionError("--help built services")

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"], services_factory=boom)
    assert exc.value.code == 0


def test_unsupported_platform_is_reported_not_raised(capsys):
    """A RuntimeError from wiring (e.g. no drivers for this OS) exits 1 with advice."""
    def unsupported():
        raise RuntimeError("Deskglow has no drivers for 'plan9' yet")

    assert cli.main(["status"], services_factory=unsupported) == 1
    assert "error: Deskglow has no drivers for 'plan9'" in capsys.readouterr().err


def test_commands_needing_a_strip_refuse_when_unconfigured(capsys, sent, services):
    """Without a saved MAC there is nothing to talk to — say so, exit 1."""
    assert run_main(["on"], services) == 1
    err = capsys.readouterr().err
    assert "No strip configured" in err
    assert "deskglow setup" in err
    assert sent == [], "a request was sent despite no strip being configured"


@pytest.mark.parametrize("argv", [["status"], ["restart-daemon"]])
def test_status_and_restart_work_without_a_configured_strip(argv, sent, services):
    """Diagnostics must stay available before/while setup is unfinished."""
    assert run_main(argv, services) == 0
    assert len(sent) == 1


def test_configured_strip_lets_normal_commands_through(sent, services):
    """Once a MAC is saved, ordinary commands are forwarded to the daemon."""
    services.storage.config["address"] = "AA:BB:CC:DD:EE:FF"
    assert run_main(["off"], services) == 0
    assert sent == [{"cmd": "off"}]


def test_env_override_counts_as_configured(sent, services):
    services.storage.override = "AA:BB:CC:DD:EE:FF"
    assert run_main(["off"], services) == 0
    assert sent == [{"cmd": "off"}]


def test_restart_daemon_leaves_the_daemon_running(monkeypatch):
    """`restart-daemon` promises a daemon that is up again afterwards."""
    running = {"up": True}

    async def fake_ensure(self):
        running["up"] = True
        return True

    def reply(req):
        # models a unit whose policy won't restart a cleanly exited service
        if req.get("cmd") == "shutdown":
            running["up"] = False
            return {"ok": True, "shutting_down": True}
        return {"ok": True}

    monkeypatch.setattr(cli.DaemonClient, "ensure_daemon", fake_ensure)
    services = make_services(ipc_client=FakeIpcClient(reply))
    assert run_main(["restart-daemon"], services) == 0
    assert running["up"], "`restart-daemon` left the daemon stopped"


def test_restart_daemon_reports_when_the_daemon_does_not_come_back(monkeypatch, capsys):
    calls = {"n": 0}

    async def ensure(self):
        calls["n"] += 1
        return calls["n"] == 1          # up for the shutdown, never again

    monkeypatch.setattr(cli.DaemonClient, "ensure_daemon", ensure)
    services = make_services(ipc_client=FakeIpcClient({"ok": True}))
    assert run_main(["restart-daemon"], services) == 1
    err = capsys.readouterr().err
    assert "could not be started again" in err and "daemon.log" in err
