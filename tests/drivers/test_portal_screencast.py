"""drivers.portal_screencast: the ScreenCast D-Bus call sequence, against a
scripted fake session bus that answers like xdg-desktop-portal."""
import pytest
from dbus_fakes import DBUS, FakeBus, Variant, reply

from deskglow.drivers import portal_screencast as pc

SESSION = "/org/freedesktop/portal/desktop/session/1_42/s1"


def portal_script(start_code=0, streams=None, restore="tok-2", missing=False):
    streams = [[57, {"size": Variant("(ii)", [2560, 1440])}]] if streams is None else streams
    results = {
        "CreateSession": (0, {"session_handle": Variant("s", SESSION)}),
        "SelectSources": (0, {}),
        "Start": (start_code, {"streams": Variant("a(ua{sv})", streams),
                               **({"restore_token": Variant("s", restore)} if restore else {})}),
    }

    def answer(bus, msg):
        if msg.member == "AddMatch":
            return reply()
        if missing:
            return reply(error="org.freedesktop.DBus.Error.ServiceUnknown")
        if msg.member in results:
            token = msg.body[-1]["handle_token"].value
            bus.emit(pc.request_path(bus.unique_name, token), "Response", list(results[msg.member]))
            return reply([pc.request_path(bus.unique_name, token)])
        if msg.member == "OpenPipeWireRemote":
            return reply([0], unix_fds=[99])
        if msg.member == "Close":
            return reply()
        raise AssertionError(msg.member)
    return answer


def tokens():
    n = iter(range(100))
    return lambda: f"t{next(n)}"


def make(**kw):
    bus = FakeBus(portal_script(**kw))
    return pc.ScreenCastPortal(bus, dbus=DBUS, token_factory=tokens()), bus


def portal_calls(bus):
    return [m for m in bus.calls if m.member != "AddMatch"]


def test_request_path_follows_the_portal_convention():
    assert pc.request_path(":1.42", "abc") == \
        "/org/freedesktop/portal/desktop/request/1_42/abc"


async def test_full_sequence_selects_one_monitor_persistently_and_opens_pipewire():
    portal, bus = make()
    stream = await portal.open("tok-1")
    create, select, start, remote = portal_calls(bus)
    assert [m.member for m in (create, select, start, remote)] == [
        "CreateSession", "SelectSources", "Start", "OpenPipeWireRemote"]
    for m in (create, select, start, remote):
        assert (m.destination, m.path, m.interface) == (
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast")
    assert create.signature == "a{sv}" and "session_handle_token" in create.body[0]
    assert select.signature == "oa{sv}" and select.body[0] == SESSION
    opts = select.body[1]
    assert opts["types"] == Variant("u", 1), "must share a MONITOR"
    assert opts["multiple"] == Variant("b", False)
    assert opts["persist_mode"] == Variant("u", 2), "must persist until revoked"
    assert opts["restore_token"] == Variant("s", "tok-1")
    assert start.signature == "osa{sv}" and start.body[:2] == [SESSION, ""]
    assert remote.signature == "oa{sv}" and remote.body == [SESSION, {}]
    assert (stream.fd, stream.node_id, stream.size, stream.restore_token) == (
        99, 57, (2560, 1440), "tok-2")
    assert bus.handlers == [], "Response handlers leaked"


async def test_every_request_subscribes_to_its_response_before_calling():
    portal, bus = make()
    await portal.open()
    members = [m.member for m in bus.calls]
    for method in ("CreateSession", "SelectSources", "Start"):
        i = members.index(method)
        assert members[i - 1] == "AddMatch", f"{method} could race its Response"
        match = bus.calls[i - 1].body[0]
        token = bus.calls[i].body[-1]["handle_token"].value
        assert pc.request_path(":1.42", token) in match


async def test_no_saved_token_means_no_restore_token_option():
    portal, bus = make()
    await portal.open(None)
    select = [m for m in bus.calls if m.member == "SelectSources"][0]
    assert "restore_token" not in select.body[1]


async def test_a_cancelled_dialog_is_a_clear_error():
    portal, _ = make(start_code=1)
    with pytest.raises(pc.PortalError, match="cancelled"):
        await portal.open()


async def test_no_streams_is_an_error():
    portal, _ = make(streams=[])
    with pytest.raises(pc.PortalError, match="no screen stream"):
        await portal.open()


async def test_a_missing_portal_names_what_to_install():
    portal, _ = make(missing=True)
    with pytest.raises(pc.PortalError, match="xdg-desktop-portal"):
        await portal.open()


async def test_close_ends_the_session_and_disconnects():
    portal, bus = make()
    await portal.open()
    await portal.close()
    close = bus.calls[-1]
    assert (close.path, close.interface, close.member) == (
        SESSION, "org.freedesktop.portal.Session", "Close")
    assert bus.disconnected == 1
    await portal.close()                      # again: never raises
