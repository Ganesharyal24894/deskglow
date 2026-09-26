"""CLI argument parsing and the mapping from a subcommand to one daemon request."""
import argparse

from .. import __version__
from ..controller.modes.patterns import pattern_names
from ..model import color as colormod
from ..model.settings import SCREEN_STYLES

PROG = "deskglow"
WARM_WHITE = (255, 180, 110)


def build_parser():
    p = argparse.ArgumentParser(prog=PROG, description="Control a Bluetooth LE RGB LED strip")
    p.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="find and save your LED strip (run this first)")
    sub.add_parser("repair", help="reset Bluetooth if the strip is stuck/unresponsive")
    sub.add_parser("on", help="turn on (warm white)")
    sub.add_parser("off", help="turn the strip off")
    sub.add_parser("toggle", help="turn off, or back on to what was lit before")
    pau = sub.add_parser("autostart", help="start the daemon when you log in (on/off/status)")
    pau.add_argument("state", choices=["on", "off", "status"])
    sub.add_parser("forget", help="stop and forget the configured strip")
    pn = sub.add_parser("name", help="rename the strip (shown in the app)")
    pn.add_argument("value", nargs="+")
    pss = sub.add_parser("sunset", help="turn the strip on at local sunset")
    pss.add_argument("state", choices=["on", "off"])
    pf = sub.add_parser("favourite", help="add/remove a favourite colour")
    pf.add_argument("action", choices=["add", "remove"])
    pf.add_argument("value", nargs="+", help="name, #rrggbb, or R G B")
    sub.add_parser("reset", help="force known-good state (on, full, solid white)")
    sub.add_parser("status", help="show daemon/strip status")

    pc = sub.add_parser("color", help="solid color: name, #rrggbb, or R G B")
    pc.add_argument("value", nargs="+")

    psc = sub.add_parser("screen", help="screen bias-light of the focused monitor")
    psc.add_argument("style", nargs="?", choices=list(SCREEN_STYLES), default=None,
                     help="color extraction style (default: keep current / vivid)")
    sub.add_parser("calm", help="calm breathing color drift")
    sub.add_parser("circadian", help="color follows time of day")

    pp = sub.add_parser("pattern", help="run a built-in effect (Lotus-style)")
    pp.add_argument("name", nargs="?", default="fade-colors", choices=pattern_names())
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
    pmo.add_argument("which", metavar="TARGET",
                     help="'focus' (the monitor with the focused window), 'both', "
                          "or an output name from `xrandr --listmonitors` "
                          "(e.g. DP-2, HDMI-A-1)")

    sub.add_parser("restart-daemon", help="restart the background daemon")
    return p


def _mode(mode, args):
    return {"cmd": "set_mode", "mode": mode, "args": args}


def to_request(args):
    c = args.cmd
    simple = {"off": {"cmd": "off"}, "reset": {"cmd": "reset"}, "status": {"cmd": "status"},
              "toggle": {"cmd": "toggle"}, "forget": {"cmd": "forget"},
              "calm": _mode("calm", {}), "circadian": _mode("circadian", {}),
              # handled by restart_daemon(), which brings it back up afterwards
              "restart-daemon": {"cmd": "shutdown"}}
    if c in simple:
        return simple[c]
    if c == "on":
        return _mode("solid", {"rgb": list(WARM_WHITE)})
    if c == "color":
        return _mode("solid", {"rgb": list(colormod.parse(args.value))})
    if c == "screen":
        return _mode("screen", {"style": args.style} if args.style else {})
    if c == "pattern":
        return _mode("pattern", {"name": args.name, "speed": args.speed})
    if c == "pomodoro":
        return _mode("pomodoro", {"work": args.work, "break": args.brk, "rounds": args.rounds})
    if c == "audio":
        a = {"target": args.target, "source": args.source}
        if args.value:
            a["rgb"] = list(colormod.parse(args.value))
        return _mode("audio", a)
    if c == "brightness":
        return {"cmd": "config", "key": "max_brightness", "value": max(0, min(100, args.pct))}
    if c == "name":
        return {"cmd": "config", "key": "strip_name", "value": " ".join(args.value)}
    if c == "sunset":
        return {"cmd": "config", "key": "sunset_on", "value": args.state == "on"}
    if c == "favourite":
        return {"cmd": f"favourite_{args.action}",
                "color": colormod.to_hex(colormod.parse(args.value))}
    if c == "monitor":
        return {"cmd": "config", "key": "screen_monitor", "value": args.which}
    raise SystemExit(f"unhandled command {c}")
