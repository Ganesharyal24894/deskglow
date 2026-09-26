"""Autostart on Windows: an HKCU ...\\CurrentVersion\\Run value that launches
the daemon with pythonw.exe (no console window) at login."""
import os
import subprocess
import sys

from .process import (CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW, DETACHED_PROCESS,
                      daemon_argv)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "Deskglow"


def pythonw(executable=None, exists=os.path.exists):
    """pythonw.exe next to the running interpreter, else the interpreter itself."""
    executable = executable or sys.executable
    candidate = os.path.join(os.path.dirname(executable), "pythonw.exe")
    return candidate if exists(candidate) else executable


def _winreg():
    import winreg
    return winreg


class WindowsRunAutostart:
    def __init__(self, winreg=None, popen=None, executable=None):
        self._reg = winreg
        self._popen = popen or subprocess.Popen
        self.argv = daemon_argv(pythonw(executable))

    @property
    def command(self):
        return subprocess.list2cmdline(self.argv)   # Windows quoting rules

    def is_enabled(self):
        reg = self._reg or _winreg()
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_READ) as key:
                reg.QueryValueEx(key, VALUE)
            return True
        except OSError:
            return False

    def set_enabled(self, enabled):
        reg = self._reg or _winreg()
        if enabled:
            with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.SetValueEx(key, VALUE, 0, reg.REG_SZ, self.command)
            return
        try:
            with reg.OpenKey(reg.HKEY_CURRENT_USER, RUN_KEY, 0, reg.KEY_SET_VALUE) as key:
                reg.DeleteValue(key, VALUE)
        except FileNotFoundError:
            pass                                   # already off

    def start(self):
        """Launch the login entry's daemon now, detached. False if not enabled
        (the client then spawns one itself) or if it could not be started."""
        if not self.is_enabled():
            return False
        try:
            self._popen(self.argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, close_fds=True,
                        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                        | CREATE_NO_WINDOW)
            return True
        except OSError:
            return False
