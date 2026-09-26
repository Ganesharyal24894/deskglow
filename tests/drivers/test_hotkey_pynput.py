"""drivers.hotkey_pynput with a fake pynput.keyboard."""
import types

from deskglow.drivers.hotkey_pynput import NoHotkey, PynputHotkey


def fake_keyboard(trusted=True, fail_start=False):
    made = []

    class GlobalHotKeys:
        def __init__(self, mapping):
            self.mapping, self.started, self.stopped, self.waited = mapping, 0, 0, 0
            if trusted is not None:
                self.IS_TRUSTED = trusted
            made.append(self)

        def start(self):
            if fail_start:
                raise OSError("no X display")
            self.started += 1

        def wait(self):
            self.waited += 1

        def stop(self):
            self.stopped += 1

    def parse(seq):
        if "<" not in seq:
            raise ValueError(seq)
        return [seq]

    kb = types.SimpleNamespace(GlobalHotKeys=GlobalHotKeys,
                               HotKey=types.SimpleNamespace(parse=parse))
    return kb, made


def test_register_starts_a_global_listener_for_the_sequence():
    kb, made = fake_keyboard()
    hk = PynputHotkey(kb)
    cb = object()
    assert hk.register("<ctrl>+<alt>+l", cb) is True
    assert made[0].mapping == {"<ctrl>+<alt>+l": cb}
    assert made[0].started == 1 and made[0].waited == 1
    hk.unregister()
    assert made[0].stopped == 1
    hk.unregister()                              # nothing registered: fine


def test_registering_again_replaces_the_previous_shortcut():
    kb, made = fake_keyboard()
    hk = PynputHotkey(kb)
    hk.register("<ctrl>+<alt>+l", print)
    hk.register("<ctrl>+<alt>+k", print)
    assert made[0].stopped == 1 and made[1].stopped == 0


def test_macos_without_accessibility_permission_reports_false(caplog):
    kb, made = fake_keyboard(trusted=False)
    assert PynputHotkey(kb).register("<cmd>+<alt>+l", print) is False
    assert made[0].stopped == 1
    assert "Accessibility" in caplog.text


def test_a_bad_sequence_or_backend_failure_reports_false():
    kb, made = fake_keyboard()
    assert PynputHotkey(kb).register("ctrl-l", print) is False
    assert made == []
    kb, _ = fake_keyboard(fail_start=True)
    assert PynputHotkey(kb).register("<ctrl>+l", print) is False


def test_pynput_not_installed_reports_false(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_pynput(name, *a, **k):
        if name.startswith("pynput"):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_pynput)
    assert PynputHotkey().register("<ctrl>+l", print) is False


def test_wayland_never_grabs_keys():
    hk = NoHotkey()
    assert hk.register("<ctrl>+<alt>+l", print) is False
    hk.unregister()
