"""ProcessControl: spawn a detached daemon, exit so a service manager restarts us."""
import os
import subprocess
import sys
import threading

DAEMON_MODULE = "deskglow.app.daemon"

# Windows creation flags (numeric fallbacks so this module imports anywhere)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def daemon_argv(executable=None):
    return [executable or sys.executable, "-m", DAEMON_MODULE]


def _pkg_root():
    """The directory containing the `deskglow` package (a checkout or site-packages)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _DetachedProcessControl:
    # Only one thread at a time may decide to spawn a daemon: clients that poll
    # on fresh threads would otherwise each fork their own daemon.
    _spawn_lock = threading.Lock()

    def __init__(self, log_path, popen=None, exit_func=None):
        self._log_path = log_path
        self._popen = popen or subprocess.Popen
        self._exit = exit_func or os._exit

    def _detach_kwargs(self):
        raise NotImplementedError

    def spawn_daemon(self):
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        # deliberately not a context manager: the handle is inherited by the
        # detached daemon process and must outlive this function.
        logf = open(self._log_path, "a")  # noqa: SIM115
        env = dict(os.environ)
        env["PYTHONPATH"] = _pkg_root() + os.pathsep + env.get("PYTHONPATH", "")
        self._popen(daemon_argv(), cwd=_pkg_root(), env=env, stdin=subprocess.DEVNULL,
                    stdout=logf, stderr=logf, **self._detach_kwargs())

    def try_begin_spawn(self):
        return self._spawn_lock.acquire(blocking=False)

    def end_spawn(self):
        self._spawn_lock.release()

    def exit_for_restart(self, code=1):
        # the service manager (systemd Restart=always, launchd KeepAlive on a
        # non-zero exit) or the next client brings us back with fresh resources
        self._exit(code)


class PosixProcessControl(_DetachedProcessControl):
    def _detach_kwargs(self):
        return {"start_new_session": True}     # survives the client's terminal


class WindowsProcessControl(_DetachedProcessControl):
    def _detach_kwargs(self):
        return {"creationflags": DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
                "close_fds": True}
