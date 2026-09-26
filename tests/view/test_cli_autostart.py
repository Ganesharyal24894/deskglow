"""`deskglow autostart on|off|status`: start-at-login from the command line."""
import pytest
from fakes import FakeAutostart, make_services

from deskglow.view import cli


def run(argv, autostart):
    services = make_services(autostart=autostart)
    return cli.main(argv, services_factory=lambda: services)


@pytest.mark.parametrize("state,enabled", [("on", True), ("off", False)])
def test_on_and_off_change_the_login_entry(capsys, state, enabled):
    auto = FakeAutostart(enabled=not enabled)
    assert run(["autostart", state], auto) == 0
    assert auto.set_calls == [enabled] and auto.enabled is enabled
    assert capsys.readouterr().out.strip() == f"start at login: {state}"


def test_status_only_reads(capsys):
    auto = FakeAutostart(enabled=True)
    assert run(["autostart", "status"], auto) == 0
    assert auto.set_calls == []
    assert capsys.readouterr().out.strip() == "start at login: on"


def test_a_refusal_is_an_error_not_a_crash(capsys):
    auto = FakeAutostart(error=OSError("launchctl said no"))
    assert run(["autostart", "on"], auto) == 1
    err = capsys.readouterr().err
    assert "could not change start at login" in err and "launchctl said no" in err


def test_works_without_a_configured_strip(capsys):
    """Autostart is about the daemon, not the strip: no `setup` needed first."""
    assert run(["autostart", "status"], FakeAutostart()) == 0
    assert "No strip configured" not in capsys.readouterr().err


def test_rejects_other_words():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["autostart", "maybe"])
