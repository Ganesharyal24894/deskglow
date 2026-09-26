"""A stand-in for the few dbus_fast names the drivers use, plus a scripted bus.

Lets the D-Bus drivers be tested on any OS (dbus-fast is Linux-only)."""
import types

ERROR, SIGNAL, RETURN = "error", "signal", "return"


class Variant:
    def __init__(self, signature, value):
        self.signature, self.value = signature, value

    def __eq__(self, other):
        return isinstance(other, Variant) and (self.signature, self.value) == (
            other.signature, other.value)

    def __repr__(self):
        return f"Variant({self.signature!r}, {self.value!r})"


def Message(**kw):
    kw.setdefault("signature", "")
    kw.setdefault("body", [])
    return types.SimpleNamespace(**kw)


DBUS = types.SimpleNamespace(
    Message=Message, Variant=Variant,
    MessageType=types.SimpleNamespace(ERROR=ERROR, SIGNAL=SIGNAL, METHOD_RETURN=RETURN),
    BusType=types.SimpleNamespace(SYSTEM="system", SESSION="session"))


def reply(body=(), error=None, unix_fds=()):
    return types.SimpleNamespace(message_type=ERROR if error else RETURN,
                                 error_name=error, body=list(body), unix_fds=list(unix_fds))


class FakeBus:
    """Answers bus.call() from `script(msg) -> reply` and records every call.
    `on_call` may emit signals to the registered handlers (like a portal)."""

    def __init__(self, script, unique_name=":1.42"):
        self.script = script
        self.unique_name = unique_name
        self.calls = []
        self.handlers = []
        self.disconnected = 0

    async def call(self, msg):
        self.calls.append(msg)
        return self.script(self, msg)

    def add_message_handler(self, fn):
        self.handlers.append(fn)

    def remove_message_handler(self, fn):
        self.handlers.remove(fn)

    def emit(self, path, member, body):
        sig = types.SimpleNamespace(message_type=SIGNAL, path=path, member=member, body=body)
        for fn in list(self.handlers):
            fn(sig)

    def disconnect(self):
        self.disconnected += 1
