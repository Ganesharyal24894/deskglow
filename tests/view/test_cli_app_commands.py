"""CLI subcommands for the settings the desktop app added."""
import pytest

from deskglow.view import cli, cli_parser


def to_req(argv):
    return cli_parser.to_request(cli_parser.build_parser().parse_args(argv))


@pytest.mark.parametrize("argv,expected", [
    (["toggle"], {"cmd": "toggle"}),
    (["forget"], {"cmd": "forget"}),
    (["name", "Shelf", "strip"], {"cmd": "config", "key": "strip_name", "value": "Shelf strip"}),
    (["sunset", "on"], {"cmd": "config", "key": "sunset_on", "value": True}),
    (["sunset", "off"], {"cmd": "config", "key": "sunset_on", "value": False}),
    (["favourite", "add", "#ff8800"], {"cmd": "favourite_add", "color": "#FF8800"}),
    (["favourite", "remove", "0", "0", "255"], {"cmd": "favourite_remove", "color": "#0000FF"}),
])
def test_new_subcommands_map_to_requests(argv, expected):
    assert to_req(argv) == expected


def test_sunset_rejects_other_words():
    with pytest.raises(SystemExit):
        cli_parser.build_parser().parse_args(["sunset", "maybe"])


def test_status_prints_the_strip_name_and_colour(capsys):
    cli.print_response({"cmd": "status"}, {"ok": True, "name": "Desk strip", "mode": "solid",
                                           "desc": "solid", "color": "#FFB46E"})
    out = capsys.readouterr().out
    assert "strip:           Desk strip" in out
    assert "colour:          #FFB46E" in out


def test_favourite_reply_prints_the_list(capsys):
    cli.print_response({"cmd": "favourite_add"}, {"ok": True, "favourites": ["#FF8800"]})
    assert "favourites = ['#FF8800']" in capsys.readouterr().out


@pytest.mark.parametrize("cmd", ["forget", "name", "sunset", "favourite"])
def test_commands_that_work_without_a_configured_strip(cmd):
    assert cmd in cli.NEEDS_NO_STRIP
