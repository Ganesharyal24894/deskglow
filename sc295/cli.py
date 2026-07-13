"""Thin CLI: translate a subcommand into one daemon request. Auto-starts the
daemon if it isn't already running, so commands are always instant afterwards."""
import argparse
import asyncio
import os
import subprocess
import sys
import time

from . import ipc, color as colormod
from .config import CONFIG_DIR, socket_path
from .modes.patterns import pattern_names

WARM_WHITE = (255, 180, 110)


def _pkg_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def _ping():
    try:
        r = await ipc.request(socket_path(), {"cmd": "ping"}, timeout=2.0)
        return bool(r and r.get("pong"))
    except Exception:
        return False


def _spawn_daemon():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logf = open(os.path.join(CONFIG_DIR, "daemon.log"), "a")
    env = dict(os.environ)
    env["PYTHONPATH"] = _pkg_root() + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.Popen(
        [sys.executable, "-m", "sc295.daemon"],
        cwd=_pkg_root(), env=env, stdout=logf, stderr=logf,
        start_new_session=True)


def _try_systemctl_start():
    """Prefer the installed systemd service so we always run the installed code
    (and don't leave a rogue CLI-spawned daemon holding the socket)."""
    try:
        r = subprocess.run(["systemctl", "--user", "start", "sc295d.service"],
                           capture_output=True, timeout=8)
        return r.returncode == 0
    except Exception:
        return False


async def _ensure_daemon():
    if await _ping():
        return True
    if _try_systemctl_start():
        for _ in range(40):
            await asyncio.sleep(0.25)
            if await _ping():
                return True
    _spawn_daemon()  # fallback if the service isn't installed
    for _ in range(40):  # wait up to ~10s
        await asyncio.sleep(0.25)
        if await _ping():
            return True
    return False


async def _send(req):
    if not await _ensure_daemon():
        print("error: could not start/reach the sc295 daemon "
              f"(see {os.path.join(CONFIG_DIR, 'daemon.log')})", file=sys.stderr)
        return 1
    resp = await ipc.request(socket_path(), req)
    if resp is None:
        print("error: no response from daemon", file=sys.stderr)
        return 1
    if not resp.get("ok"):
        print(f"error: {resp.get('error')}", file=sys.stderr)
        return 1
    _print_resp(req, resp)
    return 0


def _print_resp(req, resp):
    cmd = req.get("cmd")
    if cmd == "status":
        print(f"mode:            {resp.get('mode')}  ({resp.get('desc')})")
        print(f"BLE connected:   {resp.get('connected')}")
        print(f"screen monitor:  {resp.get('screen_monitor')}")
        print(f"max brightness:  {resp.get('max_brightness')}%")
    elif cmd == "set_mode":
        print(f"-> {resp.get('mode')} ({resp.get('desc')})")
    elif cmd == "config":
        for k, v in resp.items():
            if k != "ok":
                print(f"{k} = {v}")
    else:
        print("ok")


def build_parser():
    p = argparse.ArgumentParser(prog="sc295", description="Control the SC295 LED strip")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("on", help="turn on (warm white)")
    sub.add_parser("off", help="turn the strip off")
    sub.add_parser("reset", help="force known-good state (on, full, solid white)")
    sub.add_parser("status", help="show daemon/strip status")

    pc = sub.add_parser("color", help="solid color: name, #rrggbb, or R G B")
    pc.add_argument("value", nargs="+")

    psc = sub.add_parser("screen", help="screen bias-light of the focused monitor")
    psc.add_argument("style", nargs="?",
                     choices=["average", "vivid", "dominant", "edge"], default=None,
                     help="color extraction style (default: keep current / vivid)")
    sub.add_parser("calm", help="calm breathing color drift")
    sub.add_parser("circadian", help="color follows time of day")

    pp = sub.add_parser("pattern", help="run a built-in effect (Lotus-style)")
    pp.add_argument("name", nargs="?", default="fade-colors",
                    choices=pattern_names())
    pp.add_argument("--speed", type=int, default=50, help="effect speed 1-100")
    sub.add_parser("patterns", help="list available patterns")

    pm = sub.add_parser("pomodoro", help="focus timer via color")
    pm.add_argument("--work", type=float, default=25)
    pm.add_argument("--break", dest="brk", type=float, default=5)
    pm.add_argument("--rounds", type=int, default=4)

    pa = sub.add_parser("audio", help="audio-reactive to system sound or mic")
    pa.add_argument("value", nargs="*", help="optional fixed base color")
    pa.add_argument("--source", choices=["system", "mic"], default="system",
                    help="capture system output (default) or the microphone")
    pa.add_argument("--target", default=None, help="explicit pipewire node to capture")

    pb = sub.add_parser("brightness", help="global brightness ceiling 0-100")
    pb.add_argument("pct", type=int)

    pmo = sub.add_parser("monitor", help="which monitor screen-mode samples")
    pmo.add_argument("which", choices=["focus", "HDMI-0", "eDP-1-1", "both"])

    sub.add_parser("restart-daemon", help="tell the daemon to exit (systemd restarts it)")
    return p


def to_request(args):
    c = args.cmd
    if c == "on":
        return {"cmd": "set_mode", "mode": "solid", "args": {"rgb": list(WARM_WHITE)}}
    if c == "off":
        return {"cmd": "off"}
    if c == "reset":
        return {"cmd": "reset"}
    if c == "status":
        return {"cmd": "status"}
    if c == "color":
        rgb = colormod.parse(args.value)
        return {"cmd": "set_mode", "mode": "solid", "args": {"rgb": list(rgb)}}
    if c == "screen":
        a = {}
        if args.style:
            a["style"] = args.style
        return {"cmd": "set_mode", "mode": "screen", "args": a}
    if c == "calm":
        return {"cmd": "set_mode", "mode": "calm", "args": {}}
    if c == "circadian":
        return {"cmd": "set_mode", "mode": "circadian", "args": {}}
    if c == "pattern":
        return {"cmd": "set_mode", "mode": "pattern",
                "args": {"name": args.name, "speed": args.speed}}
    if c == "pomodoro":
        return {"cmd": "set_mode", "mode": "pomodoro",
                "args": {"work": args.work, "break": args.brk, "rounds": args.rounds}}
    if c == "audio":
        a = {"target": args.target, "source": args.source}
        if args.value:
            a["rgb"] = list(colormod.parse(args.value))
        return {"cmd": "set_mode", "mode": "audio", "args": a}
    if c == "brightness":
        return {"cmd": "config", "key": "max_brightness", "value": max(0, min(100, args.pct))}
    if c == "monitor":
        return {"cmd": "config", "key": "screen_monitor", "value": args.which}
    if c == "restart-daemon":
        return {"cmd": "shutdown"}
    raise SystemExit(f"unhandled command {c}")


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "patterns":
        print("available patterns:", ", ".join(pattern_names()))
        return 0
    req = to_request(args)
    return asyncio.run(_send(req))


if __name__ == "__main__":
    sys.exit(main())
