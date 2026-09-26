"""GlobalHotkey via `pynput` (X11, Windows, macOS), and a Wayland stand-in.

Sequences use pynput's syntax, e.g. "<ctrl>+<alt>+l". On macOS the process
needs the Accessibility (Input Monitoring) permission; without it pynput's
listener runs but sees nothing, so register() reports False.
"""
import logging

log = logging.getLogger("deskglow.hotkey")


def _keyboard():
    from pynput import keyboard
    return keyboard


class PynputHotkey:
    def __init__(self, keyboard=None):
        self._kb = keyboard
        self._listener = None

    def register(self, sequence, callback):
        self.unregister()
        try:
            kb = self._kb or _keyboard()
            kb.HotKey.parse(sequence)              # ValueError on a bad sequence
            listener = kb.GlobalHotKeys({sequence: callback})
            listener.start()
            if hasattr(listener, "wait"):
                listener.wait()                     # until the backend is ready
            if getattr(listener, "IS_TRUSTED", True) is False:
                listener.stop()
                log.warning("global shortcut %s needs the Accessibility permission "
                            "(System Settings > Privacy & Security)", sequence)
                return False
        except Exception as e:
            log.warning("cannot register global shortcut %s: %s", sequence, e)
            return False
        self._listener = listener
        return True

    def unregister(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass


class NoHotkey:
    """Wayland: compositors do not let ordinary clients grab keys globally."""

    def register(self, sequence, callback):
        return False

    def unregister(self):
        pass
