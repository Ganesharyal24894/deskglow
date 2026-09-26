"""drivers.process: spawning a detached daemon (POSIX + Windows flags), the
single-spawner claim, and exit-for-restart. Popen is always a fake."""
import os
import subprocess
import sys
import threading

import pytest

from deskglow.drivers import process


def spawn_with(cls, tmp_path, log=None):
    spawned = []
    log = log or tmp_path / "new" / "dir" / "daemon.log"
    cls(str(log), popen=lambda cmd, **kw: spawned.append((cmd, kw))).spawn_daemon()
    cmd, kw = spawned[0]
    kw["stdout"].close()
    return cmd, kw, log


def test_posix_spawn_runs_the_daemon_module_in_a_new_session(tmp_path):
    cmd, kw, log = spawn_with(process.PosixProcessControl, tmp_path)
    assert cmd == [sys.executable, "-m", "deskglow.app.daemon"]
    assert kw["start_new_session"] is True
    assert "creationflags" not in kw
    root = process._pkg_root()
    assert os.path.isdir(os.path.join(root, "deskglow"))
    assert kw["env"]["PYTHONPATH"].split(os.pathsep)[0] == root
    assert kw["cwd"] == root
    assert kw["stdin"] is subprocess.DEVNULL
    assert kw["stderr"] is kw["stdout"]
    assert log.parent.is_dir(), "the log directory was not created"


def test_windows_spawn_detaches_without_a_console(tmp_path):
    cmd, kw, _log = spawn_with(process.WindowsProcessControl, tmp_path)
    assert cmd == [sys.executable, "-m", "deskglow.app.daemon"]
    flags = kw["creationflags"]
    for flag in (0x00000008, 0x00000200, 0x08000000):   # DETACHED, NEW_GROUP, NO_WINDOW
        assert flags & flag == flag, hex(flag)
    assert "start_new_session" not in kw


@pytest.mark.parametrize("cls", [process.PosixProcessControl, process.WindowsProcessControl])
def test_spawn_daemon_appends_to_an_existing_log(tmp_path, cls):
    log = tmp_path / "daemon.log"
    log.write_text("old\n")
    spawned = []
    cls(str(log), popen=lambda cmd, **kw: spawned.append(kw)).spawn_daemon()
    spawned[0]["stdout"].write("new\n")
    spawned[0]["stdout"].close()
    assert log.read_text() == "old\nnew\n", "the daemon log was truncated"


def test_spawn_claim_is_exclusive_until_released():
    pc = process.PosixProcessControl("/unused")
    other = process.WindowsProcessControl("/unused")
    assert pc.try_begin_spawn() is True
    try:
        assert other.try_begin_spawn() is False, "a second caller could also spawn"
        seen = []
        t = threading.Thread(target=lambda: seen.append(other.try_begin_spawn()))
        t.start()
        t.join()
        assert seen == [False]
    finally:
        pc.end_spawn()
    assert other.try_begin_spawn() is True
    other.end_spawn()


@pytest.mark.parametrize("cls", [process.PosixProcessControl, process.WindowsProcessControl])
def test_exit_for_restart_exits_with_the_code(cls):
    codes = []
    cls("/unused", exit_func=codes.append).exit_for_restart(3)
    assert codes == [3]
