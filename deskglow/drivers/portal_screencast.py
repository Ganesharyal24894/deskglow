"""xdg-desktop-portal ScreenCast over D-Bus (dbus-fast), for Wayland capture.

CreateSession -> SelectSources(types=MONITOR, persist_mode=2, restore_token)
-> Start (the user picks a monitor once; the restore token skips the dialog
next time) -> OpenPipeWireRemote (a PipeWire fd). Each request's answer comes
as a Request.Response signal, subscribed to *before* the call so it can't be
missed. The bus and dbus_fast names are injectable for tests.
"""
import asyncio
import secrets
from dataclasses import dataclass

PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"
REQUEST = "org.freedesktop.portal.Request"
SOURCE_MONITOR = 1
PERSIST_UNTIL_REVOKED = 2
USER_TIMEOUT = 300.0      # the share dialog waits for a human
MISSING_PORTAL = ("the xdg-desktop-portal ScreenCast service is not available "
                  "(install xdg-desktop-portal plus your desktop's backend, e.g. "
                  "xdg-desktop-portal-gnome, -kde or -wlr)")


class PortalError(RuntimeError):
    """The portal refused, is missing, or the user cancelled."""


@dataclass
class PortalStream:
    fd: int                        # PipeWire remote, to hand to pipewiresrc
    node_id: int
    size: tuple | None             # (width, height) of the shared monitor
    restore_token: str | None      # save it: next Start skips the dialog


def _dbus_fast():
    import dbus_fast
    import dbus_fast.aio
    return dbus_fast


def request_path(unique_name, token):
    sender = unique_name.lstrip(":").replace(".", "_")
    return f"{PORTAL_PATH}/request/{sender}/{token}"


def _value(v):
    return getattr(v, "value", v)


class ScreenCastPortal:
    def __init__(self, bus, dbus=None, token_factory=None):
        self.bus = bus
        self._d = dbus or _dbus_fast()
        self._token = token_factory or (lambda: "deskglow_" + secrets.token_hex(8))
        self.session = None

    @classmethod
    async def connect(cls, dbus=None):
        dbus = dbus or _dbus_fast()
        try:
            bus = await dbus.aio.MessageBus(negotiate_unix_fd=True).connect()
        except Exception as e:
            raise PortalError(f"cannot reach the D-Bus session bus: {e}") from e
        return cls(bus, dbus)

    async def _call(self, **kw):
        kw.setdefault("destination", PORTAL)
        reply = await self.bus.call(self._d.Message(**kw))
        if reply.message_type == self._d.MessageType.ERROR:
            if "ServiceUnknown" in str(reply.error_name) or "UnknownMethod" in str(reply.error_name):
                raise PortalError(MISSING_PORTAL)
            raise PortalError(f"{kw['member']} failed: {reply.error_name} {reply.body}")
        return reply

    async def _request(self, member, signature, args, options):
        token = self._token()
        options = {**options, "handle_token": self._d.Variant("s", token)}
        path = request_path(self.bus.unique_name, token)
        fut = asyncio.get_running_loop().create_future()

        def on_message(msg):
            if (msg.message_type == self._d.MessageType.SIGNAL and msg.path == path
                    and msg.member == "Response" and not fut.done()):
                fut.set_result(msg.body)

        self.bus.add_message_handler(on_message)
        try:
            await self._call(destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
                             interface="org.freedesktop.DBus", member="AddMatch",
                             signature="s", body=[f"type='signal',interface='{REQUEST}',"
                                                  f"member='Response',path='{path}'"])
            await self._call(path=PORTAL_PATH, interface=SCREENCAST, member=member,
                             signature=signature, body=[*args, options])
            code, results = await asyncio.wait_for(fut, USER_TIMEOUT)
        finally:
            self.bus.remove_message_handler(on_message)
        if code == 1:
            raise PortalError("screen sharing was cancelled in the portal dialog")
        if code != 0:
            raise PortalError(f"the portal refused {member} (code {code})")
        return results

    async def open(self, restore_token=None):
        V = self._d.Variant
        res = await self._request("CreateSession", "a{sv}", [],
                                  {"session_handle_token": V("s", self._token())})
        self.session = str(_value(res["session_handle"]))
        opts = {"types": V("u", SOURCE_MONITOR), "multiple": V("b", False),
                "persist_mode": V("u", PERSIST_UNTIL_REVOKED)}
        if restore_token:
            opts["restore_token"] = V("s", restore_token)
        await self._request("SelectSources", "oa{sv}", [self.session], opts)
        res = await self._request("Start", "osa{sv}", [self.session, ""], {})
        streams = _value(res.get("streams")) or []
        if not streams:
            raise PortalError("the portal started no screen stream")
        node_id, props = streams[0][0], _value(streams[0][1]) or {}
        size = _value(props.get("size"))
        reply = await self._call(path=PORTAL_PATH, interface=SCREENCAST,
                                 member="OpenPipeWireRemote", signature="oa{sv}",
                                 body=[self.session, {}])
        fd = reply.unix_fds[reply.body[0]]
        token = _value(res.get("restore_token"))
        return PortalStream(fd, int(node_id), tuple(size) if size else None, token)

    async def close(self):
        """End the session (stops the screen-share indicator). Never raises."""
        try:
            if self.session:
                await self._call(path=self.session, interface="org.freedesktop.portal.Session",
                                 member="Close")
        except Exception:
            pass
        finally:
            self.session = None
            try:
                self.bus.disconnect()
            except Exception:
                pass
