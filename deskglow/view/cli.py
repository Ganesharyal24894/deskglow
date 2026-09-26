"""Thin CLI: translate a subcommand into one daemon request. Auto-starts the
daemon if it isn't already running, so commands are always instant afterwards."""
import asyncio
import sys

from ..controller.client import DaemonClient
from ..controller.discovery import scan_candidates
from ..controller.modes.patterns import pattern_names
from ..controller.settings import SettingsStore
from ..services.link import AdapterError
from .cli_parser import PROG, build_parser, to_request

NEEDS_NO_STRIP = ("status", "restart-daemon", "forget", "name", "sunset", "favourite")


def print_response(req, resp):
    cmd = req.get("cmd")
    if cmd == "status":
        if resp.get("name"):
            print(f"strip:           {resp.get('name')}")
        print(f"mode:            {resp.get('mode')}  ({resp.get('desc')})")
        if resp.get("color"):
            print(f"colour:          {resp.get('color')}")
        print(f"BLE connected:   {resp.get('connected')}")
        print(f"screen monitor:  {resp.get('screen_monitor')}")
        print(f"max brightness:  {resp.get('max_brightness')}%")
    elif cmd == "set_mode":
        print(f"-> {resp.get('mode')} ({resp.get('desc')})")
    elif cmd in ("config", "favourite_add", "favourite_remove"):
        for k, v in resp.items():
            if k != "ok":
                print(f"{k} = {v}")
    else:
        print("ok")


class Cli:
    """The CLI's actions, against injected services."""

    def __init__(self, services):
        self.services = services
        self.settings = SettingsStore(services.storage)
        self.client = DaemonClient(services.ipc_client, services.autostart, services.process)

    def _log_hint(self):
        return f"(see {self.services.storage.log_path()})"

    async def send(self, req):
        if not await self.client.ensure_daemon():
            print(f"error: could not start/reach the {PROG} daemon {self._log_hint()}",
                  file=sys.stderr)
            return 1
        resp = await self.client.request(req)
        if resp is None:
            print("error: no response from daemon", file=sys.stderr)
            return 1
        if not resp.get("ok"):
            print(f"error: {resp.get('error')}", file=sys.stderr)
            return 1
        print_response(req, resp)
        return 0

    async def restart_daemon(self):
        """Stop the daemon and make sure one is running again afterwards.

        A plain shutdown exits cleanly, and a service manager restart policy may
        not bring a cleanly-exited service back — so we start it again ourselves.
        """
        rc = await self.send({"cmd": "shutdown"})
        if rc != 0:
            return rc
        if not await self.client.ensure_daemon():
            print("error: the daemon stopped but could not be started again "
                  f"{self._log_hint()}", file=sys.stderr)
            return 1
        print("daemon restarted")
        return 0

    def setup(self):
        from .cli_setup import run_setup
        return run_setup(self)

    def repair(self):
        """Recover a stuck Bluetooth adapter: reset it, drop the stale bond, reconnect.
        Use when the strip shows 'connected' but won't respond, or won't connect."""
        print("Repairing Bluetooth… (this briefly resets your Bluetooth adapter)")
        try:
            self.services.link.reset_adapter(self.settings.get_address())
        except AdapterError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print("Adapter reset. Reconnecting the strip…")
        asyncio.run(self.send({"cmd": "reload"}))
        print(f"Done. Give it a few seconds; check with:  {PROG} status")
        return 0

    def autostart(self, state):
        """Turn start-at-login on/off (via the Autostart service), or report it."""
        auto = self.services.autostart
        try:
            if state != "status":
                auto.set_enabled(state == "on")
            enabled = auto.is_enabled()
        except Exception as e:
            print(f"error: could not {'change' if state != 'status' else 'read'} "
                  f"start at login: {e}", file=sys.stderr)
            return 1
        print(f"start at login: {'on' if enabled else 'off'}")
        return 0

    def scan(self, timeout=10.0):
        return asyncio.run(scan_candidates(self.services.scanner, timeout,
                                           self.services.preset))


def main(argv=None, services_factory=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "patterns":
        print("available patterns:", ", ".join(pattern_names()))
        return 0
    try:
        cli = Cli(services_factory())
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.cmd == "setup":
        return cli.setup()
    if args.cmd == "repair":
        return cli.repair()
    if args.cmd == "autostart":
        return cli.autostart(args.state)
    # everything else needs a configured strip
    if args.cmd not in NEEDS_NO_STRIP and not cli.settings.get_address():
        print(f"No strip configured yet. Run:  {PROG} setup", file=sys.stderr)
        return 1
    if args.cmd == "restart-daemon":
        return asyncio.run(cli.restart_daemon())
    return asyncio.run(cli.send(to_request(args)))
