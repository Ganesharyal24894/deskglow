"""drivers.location_tz (zone -> coordinates) and drivers.session_linux."""
import types

import pytest

from deskglow.drivers import location_tz as lt
from deskglow.drivers import session_linux

TAB = """# tzdb timezone descriptions
#codes\tcoordinates\tTZ\tcomments
DE,DK,NO,SE,SJ\t+5230+01322\tEurope/Berlin\tmost of Germany
IN\t+2232+08822\tAsia/Kolkata
US\t+404251-0740023\tAmerica/New_York\tEastern (most areas)
AU\t-3352+15113\tAustralia/Sydney\tNew South Wales (most areas)
broken line
"""


def test_iso6709_coordinates_in_both_precisions_and_hemispheres():
    assert lt.parse_coord("+5230+01322") == pytest.approx((52.5, 13.3667), abs=1e-3)
    assert lt.parse_coord("+404251-0740023") == pytest.approx((40.7142, -74.0064), abs=1e-3)
    assert lt.parse_coord("-3352+15113") == pytest.approx((-33.8667, 151.2167), abs=1e-3)
    assert lt.parse_coord("junk") is None


def test_tab_parsing_skips_comments_and_junk():
    zones = lt.parse_tab(TAB)
    assert set(zones) == {"Europe/Berlin", "Asia/Kolkata", "America/New_York",
                          "Australia/Sydney"}


@pytest.mark.parametrize("path,zone", [
    ("/usr/share/zoneinfo/Europe/Berlin", "Europe/Berlin"),
    ("/var/db/timezone/zoneinfo/America/New_York", "America/New_York"),
    ("/usr/share/zoneinfo/posix/Asia/Kolkata", "Asia/Kolkata"),
    ("C:\\tzdata\\zoneinfo\\Europe\\Berlin", "Europe/Berlin"),
    ("/etc/localtime", None)])
def test_zone_from_a_localtime_link_target(path, zone):
    assert lt.zone_from_path(path) == zone


def test_local_zone_sources_per_platform():
    link = lambda p: "/usr/share/zoneinfo/Europe/Berlin"  # noqa: E731
    assert lt.local_zone({"TZ": ":Asia/Kolkata"}, "linux", link) == "Asia/Kolkata"
    assert lt.local_zone({"TZ": "/usr/share/zoneinfo/Asia/Kolkata"}, "linux", link) == \
        "Asia/Kolkata"
    assert lt.local_zone({}, "darwin", link) == "Europe/Berlin"
    assert lt.local_zone({}, "win32", link, tzlocal_name=lambda: "Asia/Calcutta") == \
        "Asia/Calcutta"
    assert lt.local_zone({}, "win32", link, tzlocal_name=lambda: 1 / 0) is None


def location(tmp_path, zone, text=TAB):
    tab = tmp_path / "zone1970.tab"
    tab.write_text(text)
    return lt.TzLocation(zone=lambda: zone,
                         candidates=lambda: [str(tmp_path / "missing.tab"), str(tab)])


def test_location_is_the_zones_coordinates(tmp_path):
    assert location(tmp_path, "Europe/Berlin")() == pytest.approx((52.5, 13.3667), abs=1e-3)


def test_legacy_windows_names_are_mapped(tmp_path):
    assert location(tmp_path, "Asia/Calcutta")() == pytest.approx((22.5333, 88.3667), abs=1e-3)


@pytest.mark.parametrize("zone", [None, "", "Etc/UTC", "Mars/Olympus"])
def test_unknown_zones_give_none(tmp_path, zone):
    assert location(tmp_path, zone)() is None


def test_candidates_include_the_tzdata_package_when_present(tmp_path):
    paths = lt.tab_candidates(dirs=("/z",), tzdata_dir=lambda: "/pkg/tzdata/zoneinfo")
    assert paths[:2] == [lt.os.path.join("/z", "zone1970.tab"),
                         lt.os.path.join("/pkg/tzdata/zoneinfo", "zone1970.tab")]
    assert lt.tab_candidates(dirs=("/z",), tzdata_dir=lambda: 1 / 0) == [
        lt.os.path.join("/z", "zone1970.tab"), lt.os.path.join("/z", "zone.tab")]


@pytest.mark.parametrize("env,user_env,expected", [
    ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, {}, True),
    ({"XDG_SESSION_TYPE": "wayland"}, {}, True),
    ({"DISPLAY": ":1"}, {"WAYLAND_DISPLAY": "wayland-0"}, False),
    ({"XDG_SESSION_TYPE": "x11"}, {}, False),
    ({}, {"WAYLAND_DISPLAY": "wayland-0"}, True),       # daemon started early
    ({}, {"DISPLAY": ":0"}, False),
    ({}, {}, False)])
def test_session_detection(env, user_env, expected):
    assert session_linux.is_wayland(env, user_env=lambda: user_env) is expected


def test_systemd_user_env_parsing_and_failure():
    run = lambda *a, **k: types.SimpleNamespace(stdout="A=1\nB=x=y\njunk\n")  # noqa: E731
    assert session_linux.systemd_user_env(run) == {"A": "1", "B": "x=y"}

    def missing(*a, **k):
        raise FileNotFoundError("systemctl")
    assert session_linux.systemd_user_env(missing) == {}
