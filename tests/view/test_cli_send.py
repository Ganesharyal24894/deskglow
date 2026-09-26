"""deskglow.view.cli.Cli.send(): reply handling and human-readable output."""
import pytest
from fakes import FakeIpcClient, make_services

from deskglow.view import cli


# ------------------------------------------------------------------ send() ---

@pytest.fixture
def fake_daemon():
    """A Cli whose daemon is reachable (or not) and whose reply is scripted."""
    box = {"reply": {"ok": True}, "reachable": True}
    ipc = FakeIpcClient(lambda req: box["reply"])
    c = cli.Cli(make_services(ipc_client=ipc))

    async def fake_ensure():
        return box["reachable"]

    c.client.ensure_daemon = fake_ensure
    box["cli"], box["requests"] = c, ipc.requests
    return box


async def test_send_returns_zero_on_ok(fake_daemon, capsys):
    """A successful command exits 0 and prints a short confirmation."""
    assert await fake_daemon["cli"].send({"cmd": "off"}) == 0
    assert capsys.readouterr().out.strip() == "ok"


async def test_send_prints_status_report(fake_daemon, capsys):
    """`status` renders the daemon's fields as a readable summary."""
    fake_daemon["reply"] = {"ok": True, "mode": "calm", "desc": "calm",
                            "connected": True, "screen_monitor": "focus",
                            "max_brightness": 65}
    assert await fake_daemon["cli"].send({"cmd": "status"}) == 0
    out = capsys.readouterr().out
    assert "mode:            calm  (calm)" in out
    assert "BLE connected:   True" in out
    assert "screen monitor:  focus" in out
    assert "max brightness:  65%" in out


async def test_send_prints_the_new_mode(fake_daemon, capsys):
    """A mode change echoes what the daemon actually started."""
    fake_daemon["reply"] = {"ok": True, "mode": "solid", "desc": "solid (255, 0, 0)"}
    assert await fake_daemon["cli"].send({"cmd": "set_mode", "mode": "solid"}) == 0
    assert capsys.readouterr().out.strip() == "-> solid (solid (255, 0, 0))"


async def test_send_prints_config_settings(fake_daemon, capsys):
    """`config` echoes the stored key/value, and nothing else."""
    fake_daemon["reply"] = {"ok": True, "max_brightness": 40}
    req = {"cmd": "config", "key": "max_brightness", "value": 40}
    assert await fake_daemon["cli"].send(req) == 0
    assert capsys.readouterr().out.strip() == "max_brightness = 40"


async def test_send_reports_a_daemon_side_error(fake_daemon, capsys):
    """ok:False becomes exit 1 plus the daemon's own message on stderr."""
    fake_daemon["reply"] = {"ok": False, "error": "strip unreachable: timeout"}
    assert await fake_daemon["cli"].send({"cmd": "reset"}) == 1
    captured = capsys.readouterr()
    assert "error: strip unreachable: timeout" in captured.err
    assert captured.out == ""


async def test_send_reports_an_unreachable_daemon(fake_daemon, capsys):
    """If the daemon cannot be started at all, say where to look and exit 1."""
    fake_daemon["reachable"] = False
    assert await fake_daemon["cli"].send({"cmd": "status"}) == 1
    err = capsys.readouterr().err
    assert "could not start/reach the deskglow daemon" in err
    assert "/fake/config/deskglow/daemon.log" in err
    assert fake_daemon["requests"] == []


async def test_send_reports_an_empty_reply(fake_daemon, capsys):
    """A daemon that closes the socket without answering is an error, not a crash."""
    fake_daemon["reply"] = None
    assert await fake_daemon["cli"].send({"cmd": "status"}) == 1
    assert "no response from daemon" in capsys.readouterr().err
