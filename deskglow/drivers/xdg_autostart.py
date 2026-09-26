"""Start-at-login via an XDG autostart entry (~/.config/autostart/*.desktop),
for Linux desktops without a systemd user manager."""
import os

from .process import daemon_argv

DESKTOP_NAME = "deskglowd.desktop"
TEMPLATE = """\
[Desktop Entry]
Type=Application
Name=Deskglow daemon
Comment=Keeps the Bluetooth LED strip connected
Exec={exec_line}
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
"""


def quote_argv(argv):
    """Join argv for systemd ExecStart= / desktop Exec= (both accept "..." quoting)."""
    out = []
    for arg in argv:
        if any(c in arg for c in ' \t"\\'):
            arg = '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
        out.append(arg)
    return " ".join(out)


class XdgAutostart:
    def __init__(self, autostart_dir=None, executable=None, env=None):
        env = os.environ if env is None else env
        base = env.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        self.dir = autostart_dir or os.path.join(base, "autostart")
        self.path = os.path.join(self.dir, DESKTOP_NAME)
        self._executable = executable

    def start(self):
        return False          # nothing to start: the client spawns the daemon itself

    def is_enabled(self):
        return os.path.isfile(self.path)

    def set_enabled(self, enabled):
        if enabled:
            os.makedirs(self.dir, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(TEMPLATE.format(exec_line=quote_argv(daemon_argv(self._executable))))
        elif os.path.exists(self.path):
            os.unlink(self.path)
