"""AppContext: requests, errors, and the accent being set before repaints."""
from gui_fakes import push

from deskglow.view.gui import accent


def test_a_failed_request_is_reported(ctx, client):
    client.replies["reset"] = {"ok": False, "error": "strip unreachable"}
    errors, replies = [], []
    ctx.error.connect(errors.append)
    ctx.send({"cmd": "reset"}, replies.append)
    assert errors == ["strip unreachable"] and ctx.last_error == "strip unreachable"
    assert replies == [{"ok": False, "error": "strip unreachable"}]


def test_send_refreshes_status_unless_told_not_to(ctx, client):
    ctx.send({"cmd": "scan"}, refresh=False)
    assert client.requests == [{"cmd": "scan"}]
    ctx.send({"cmd": "reset"})
    assert client.requests[-1] == {"cmd": "status"}


def test_accent_is_updated_before_screens_hear_about_the_status(ctx, client):
    seen = []
    ctx.status_changed.connect(lambda s: seen.append(accent.accent()))
    changes = []
    ctx.accent_changed.connect(changes.append)
    push(ctx, client, color="#5B8CFF")
    assert seen == ["#5B8CFF"] and changes == ["#5B8CFF"]
    push(ctx, client, color="#5B8CFF")
    assert changes == ["#5B8CFF"], "no restyle when the colour didn't change"


def test_log_path_comes_from_storage(ctx):
    assert ctx.log_path() == "/fake/config/deskglow/daemon.log"
    ctx.services = None
    assert ctx.log_path() == ""
