"""Autostart via a systemd --user unit (`deskglowd.service`), falling back to
an XDG autostart entry when there is no systemd user manager."""
import os
import subprocess

from .process import daemon_argv
from .xdg_autostart import XdgAutostart, quote_argv

UNIT = "deskglowd.service"

UNIT_TEMPLATE = """\
[Unit]
Description=Deskglow LED strip daemon
After=bluetooth.target graphical-session.target
Wants=bluetooth.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
# always, not on-failure: 'deskglow restart-daemon' asks the daemon to exit
# cleanly, and an on-failure policy would leave it stopped.
Restart=always
RestartSec=3

[Install]
WantedBy=graphical-session.target
"""


def config_home(env=None):
    env = os.environ if env is None else env
    return env.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def unit_text(executable=None):
    return UNIT_TEMPLATE.format(exec_start=quote_argv(daemon_argv(executable)))


class SystemdAutostart:
    """Starts / enables `deskglowd.service` so the installed code runs."""

    def __init__(self, unit=UNIT, run=None, unit_dir=None, xdg=None, executable=None):
        self.unit = unit
        self._run = run or subprocess.run
        self.unit_dir = unit_dir or os.path.join(config_home(), "systemd", "user")
        self.unit_file = os.path.join(self.unit_dir, unit)
        self._xdg = xdg or XdgAutostart(executable=executable)
        self._executable = executable

    def _systemctl(self, *args):
        try:
            return self._run(["systemctl", "--user", *args], capture_output=True, timeout=8)
        except Exception:
            return None

    def _ok(self, *args):
        r = self._systemctl(*args)
        return r is not None and r.returncode == 0

    def available(self):
        """True if a systemd user manager answers (not the case in some
        containers, WSL, or non-systemd distros)."""
        return self._ok("show-environment")

    def start(self):
        return self._ok("start", self.unit)

    def is_enabled(self):
        return self._ok("is-enabled", self.unit) or self._xdg.is_enabled()

    def _write_unit(self):
        os.makedirs(self.unit_dir, exist_ok=True)
        with open(self.unit_file, "w", encoding="utf-8") as f:
            f.write(unit_text(self._executable))

    def set_enabled(self, enabled):
        if not self.available():
            self._xdg.set_enabled(enabled)
            return
        if enabled:
            if not os.path.exists(self.unit_file):
                self._write_unit()
            self._systemctl("daemon-reload")
            r = self._systemctl("enable", self.unit)
        else:
            r = self._systemctl("disable", self.unit)
            self._xdg.set_enabled(False)        # and any fallback entry
        if r is None or r.returncode != 0:
            err = (getattr(r, "stderr", b"") or b"").decode(errors="replace").strip()
            raise OSError(f"systemctl --user {'enable' if enabled else 'disable'} "
                          f"{self.unit} failed{': ' + err if err else ''}")
