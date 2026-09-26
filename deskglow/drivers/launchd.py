"""Autostart on macOS: a per-user LaunchAgent run in the Aqua (GUI) session."""
import os
import plistlib
import subprocess

from .process import daemon_argv

LABEL = "io.deskglow.daemon"


def agent_plist(log_dir, executable=None):
    log = os.path.join(log_dir, "daemon.log")
    return {
        "Label": LABEL,
        "ProgramArguments": daemon_argv(executable),
        "RunAtLoad": True,
        # restart after a crash or exit_for_restart (non-zero), not a clean stop
        "KeepAlive": {"SuccessfulExit": False},
        # only in the logged-in GUI session: screen capture and Bluetooth
        # permissions belong to it
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive",
        "StandardOutPath": log,
        "StandardErrorPath": log,
    }


class LaunchdAutostart:
    def __init__(self, log_dir, agents_dir=None, run=None, uid=None, executable=None):
        self.log_dir = log_dir
        agents_dir = agents_dir or os.path.join(os.path.expanduser("~"), "Library",
                                                "LaunchAgents")
        self.agents_dir = agents_dir
        self.path = os.path.join(agents_dir, LABEL + ".plist")
        self._run = run or subprocess.run
        self._uid = uid if uid is not None else getattr(os, "getuid", lambda: 0)()
        self._executable = executable

    @property
    def domain(self):
        return f"gui/{self._uid}"

    def _launchctl(self, *args):
        try:
            return self._run(["launchctl", *args], capture_output=True, timeout=10)
        except Exception:
            return None

    def start(self):
        """Kick the loaded agent (restarting it if it runs). False if not installed."""
        if not os.path.exists(self.path):
            return False
        r = self._launchctl("kickstart", f"{self.domain}/{LABEL}")
        if r is not None and r.returncode == 0:
            return True
        r = self._launchctl("bootstrap", self.domain, self.path)    # not loaded yet
        return r is not None and r.returncode == 0

    def is_enabled(self):
        return os.path.isfile(self.path)

    def set_enabled(self, enabled):
        if enabled:
            os.makedirs(self.agents_dir, exist_ok=True)
            os.makedirs(self.log_dir, exist_ok=True)
            with open(self.path, "wb") as f:
                plistlib.dump(agent_plist(self.log_dir, self._executable), f)
            self._launchctl("bootout", f"{self.domain}/{LABEL}")    # reload if loaded
            r = self._launchctl("bootstrap", self.domain, self.path)
            if r is None or r.returncode != 0:
                err = (getattr(r, "stderr", b"") or b"").decode(errors="replace").strip()
                raise OSError(f"launchctl bootstrap failed{': ' + err if err else ''}")
        else:
            self._launchctl("bootout", f"{self.domain}/{LABEL}")
            if os.path.exists(self.path):
                os.unlink(self.path)
