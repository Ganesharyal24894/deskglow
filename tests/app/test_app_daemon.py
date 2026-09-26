"""deskglow.app.daemon: log formatting and signal wiring for `deskglowd`."""
import asyncio
import io
import logging
import signal
import sys

import pytest
from fakes import make_services

from deskglow.app import daemon as app_daemon
from deskglow.drivers.ipc_tcp import TcpIpcClient, TcpIpcServer
from deskglow.drivers.ipc_unix import UnixIpcClient, UnixIpcServer


def ipc_pair(tmp_path):
    """The IPC this OS really uses: AF_UNIX, or loopback TCP on Windows."""
    if sys.platform == "win32":
        path = tmp_path / "d.json"
        return path, TcpIpcServer(str(path)), TcpIpcClient(str(path))
    path = tmp_path / "d.sock"
    return path, UnixIpcServer(str(path)), UnixIpcClient(str(path))


@pytest.fixture
def clean_logger():
    logger = logging.getLogger("deskglow")
    saved = (list(logger.handlers), logger.level, logger.propagate)
    logger.handlers.clear()
    yield logger
    logger.handlers[:] = saved[0]
    logger.setLevel(saved[1])
    logger.propagate = saved[2]


def test_configure_logging_prefixes_lines_for_the_journal(clean_logger):
    stream = io.StringIO()
    app_daemon.configure_logging(stream)
    logging.getLogger("deskglow.daemon").info("listening on /x")
    assert stream.getvalue() == "[deskglowd] listening on /x\n"


def test_configure_logging_is_idempotent(clean_logger):
    stream = io.StringIO()
    app_daemon.configure_logging(stream)
    app_daemon.configure_logging(stream)
    logging.getLogger("deskglow").info("once")
    assert stream.getvalue().count("once") == 1
    assert len(clean_logger.handlers) == 1


async def test_run_serves_and_stops_on_sigterm_or_sigint(tmp_path, monkeypatch):
    """SIGTERM (systemd stop) and SIGINT (Ctrl-C) both shut the daemon down."""
    handlers = {}
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler",
                        lambda sig, cb, *a: handlers.__setitem__(sig, cb))
    endpoint, server, client = ipc_pair(tmp_path)
    services = make_services(ipc_server=server, ipc_client=client)
    for sig in (signal.SIGTERM, signal.SIGINT):
        handlers.clear()
        task = asyncio.ensure_future(app_daemon.run(services))
        for _ in range(200):
            if sig in handlers and endpoint.exists():
                break
            await asyncio.sleep(0.01)
        assert set(handlers) == {signal.SIGTERM, signal.SIGINT}
        handlers[sig]()
        await asyncio.wait_for(task, timeout=5.0)
        assert not endpoint.exists()


def test_without_stderr_the_log_goes_to_the_log_file(clean_logger, tmp_path, monkeypatch):
    """pythonw.exe (the Windows Run-key daemon) has no stderr at all."""
    monkeypatch.setattr(sys, "stderr", None)
    log = tmp_path / "logs" / "daemon.log"
    app_daemon.configure_logging(log_path=str(log))
    logging.getLogger("deskglow.daemon").info("hello")
    for h in clean_logger.handlers:
        h.flush()
        h.close()
    assert log.read_text(encoding="utf-8") == "[deskglowd] hello\n"


def test_main_logs_to_the_services_log_path(clean_logger, monkeypatch):
    seen = {}
    services = make_services()
    monkeypatch.setattr(app_daemon, "build_services", lambda: services)
    monkeypatch.setattr(app_daemon, "configure_logging",
                        lambda **kw: seen.update(kw))

    async def fake_run(s):
        seen["ran"] = s
    monkeypatch.setattr(app_daemon, "run", fake_run)
    app_daemon.main()
    assert seen == {"log_path": services.storage.log_path(), "ran": services}
