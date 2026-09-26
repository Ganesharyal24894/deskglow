"""Console script `deskglowd`: the background daemon (run at login by the
systemd user unit, the macOS LaunchAgent or the Windows Run key)."""
import asyncio
import contextlib
import logging
import os
import signal
import sys

from ..controller.daemon import Daemon
from .wiring import build_services


def _handler(stream, log_path):
    """stderr normally; the log file when there is no stderr (pythonw.exe
    launched from the Windows Run key has none)."""
    stream = stream or sys.stderr
    if stream is None and log_path:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        return logging.FileHandler(log_path, encoding="utf-8")
    return logging.StreamHandler(stream)


def configure_logging(stream=None, log_path=None):
    """Daemon log lines go to stderr as `[deskglowd] message`."""
    logger = logging.getLogger("deskglow")
    if not logger.handlers:
        handler = _handler(stream, log_path)
        handler.setFormatter(logging.Formatter("[deskglowd] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


async def run(services):
    daemon = Daemon(services)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, daemon.request_stop)
    await daemon.serve()


def main():
    services = build_services()
    configure_logging(log_path=services.storage.log_path())
    try:
        asyncio.run(run(services))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
