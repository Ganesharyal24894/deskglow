"""deskglow.view.cli_parser: argument parsing and subcommand -> request mapping."""
import pytest

from deskglow.view import cli_parser


def parse(argv):
    return cli_parser.build_parser().parse_args(argv)


def to_req(argv):
    return cli_parser.to_request(parse(argv))


SUBCOMMANDS = ["setup", "repair", "on", "off", "reset", "status", "color",
               "screen", "calm", "circadian", "pattern", "patterns",
               "pomodoro", "audio", "brightness", "monitor", "restart-daemon"]


@pytest.mark.parametrize("argv,expected", [
    (["on"], {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 180, 110]}}),
    (["off"], {"cmd": "off"}),
    (["reset"], {"cmd": "reset"}),
    (["status"], {"cmd": "status"}),
    # colour: by name, by hex (with and without the '#' zsh eats), by triple
    (["color", "red"], {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 0, 0]}}),
    (["color", "#ff8800"], {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 136, 0]}}),
    (["color", "ff8800"], {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 136, 0]}}),
    (["color", "10", "20", "30"], {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [10, 20, 30]}}),
    # screen: no style keeps whatever the daemon already remembers
    (["screen"], {"cmd": "set_mode", "mode": "screen", "args": {}}),
    (["screen", "edge"], {"cmd": "set_mode", "mode": "screen", "args": {"style": "edge"}}),
    (["calm"], {"cmd": "set_mode", "mode": "calm", "args": {}}),
    (["circadian"], {"cmd": "set_mode", "mode": "circadian", "args": {}}),
    (["pattern"], {"cmd": "set_mode", "mode": "pattern",
                   "args": {"name": "fade-colors", "speed": 50}}),
    (["pattern", "blink-red", "--speed", "20"],
     {"cmd": "set_mode", "mode": "pattern", "args": {"name": "blink-red", "speed": 20}}),
    (["pomodoro"], {"cmd": "set_mode", "mode": "pomodoro",
                    "args": {"work": 25.0, "break": 5.0, "rounds": 4}}),
    (["pomodoro", "--work", "50", "--break", "10", "--rounds", "2"],
     {"cmd": "set_mode", "mode": "pomodoro",
      "args": {"work": 50.0, "break": 10.0, "rounds": 2}}),
    (["audio"], {"cmd": "set_mode", "mode": "audio",
                 "args": {"target": None, "source": "system"}}),
    (["audio", "--source", "mic", "--target", "alsa_output.monitor"],
     {"cmd": "set_mode", "mode": "audio",
      "args": {"target": "alsa_output.monitor", "source": "mic"}}),
    (["audio", "blue"], {"cmd": "set_mode", "mode": "audio",
                         "args": {"target": None, "source": "system", "rgb": [0, 0, 255]}}),
    (["brightness", "55"], {"cmd": "config", "key": "max_brightness", "value": 55}),
    (["monitor", "focus"], {"cmd": "config", "key": "screen_monitor", "value": "focus"}),
    (["monitor", "both"], {"cmd": "config", "key": "screen_monitor", "value": "both"}),
    (["restart-daemon"], {"cmd": "shutdown"}),
])
def test_subcommand_maps_to_request(argv, expected):
    """Each subcommand translates to exactly one well-formed daemon request."""
    assert to_req(argv) == expected


@pytest.mark.parametrize("pct,expected", [(0, 0), (100, 100), (150, 100), (-20, 0)])
def test_brightness_percentage_is_clamped(pct, expected):
    """A silly percentage is clamped rather than passed through to the strip."""
    assert to_req(["brightness", str(pct)])["value"] == expected


def test_unknown_color_name_is_rejected():
    """A colour we cannot parse must fail loudly instead of guessing."""
    with pytest.raises(ValueError):
        to_req(["color", "chartreuse-ish"])


def test_unknown_subcommand_exits_with_usage_error():
    """argparse refuses commands that don't exist (exit code 2)."""
    with pytest.raises(SystemExit) as exc:
        parse(["frobnicate"])
    assert exc.value.code == 2


@pytest.mark.parametrize("name", ["DP-2", "HDMI-A-1", "DisplayPort-0"])
def test_monitor_accepts_any_display_name(name):
    """A monitor name is machine-specific; the CLI must accept whatever xrandr reports."""
    assert to_req(["monitor", name]) == {"cmd": "config", "key": "screen_monitor",
                                         "value": name}


def test_top_level_help_exits_zero():
    """`deskglow --help` is a success, not an error."""
    with pytest.raises(SystemExit) as exc:
        parse(["--help"])
    assert exc.value.code == 0


@pytest.mark.parametrize("sub", SUBCOMMANDS)
def test_each_subcommand_help_exits_zero(sub):
    """Every subcommand documents itself without blowing up."""
    with pytest.raises(SystemExit) as exc:
        parse([sub, "--help"])
    assert exc.value.code == 0


def test_prog_name_is_deskglow(capsys):
    with pytest.raises(SystemExit):
        parse(["--version"])
    assert capsys.readouterr().out.startswith("deskglow ")
