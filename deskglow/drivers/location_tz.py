"""LocationHint from the time zone: the IANA zone's coordinates in the tz
database (zone1970.tab / zone.tab). No network, no GPS; None on any failure."""
import os
import re
import sys

ZONEINFO_DIRS = ("/usr/share/zoneinfo", "/usr/lib/zoneinfo", "/usr/share/lib/zoneinfo",
                 "/var/db/timezone/zoneinfo")
TAB_FILES = ("zone1970.tab", "zone.tab")
# Legacy names still returned by Windows/CLDR mappings, and their tab names.
ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata", "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Saigon": "Asia/Ho_Chi_Minh", "Asia/Rangoon": "Asia/Yangon",
    "Europe/Kiev": "Europe/Kyiv", "Atlantic/Faeroe": "Atlantic/Faroe",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "Asia/Istanbul": "Europe/Istanbul", "Australia/ACT": "Australia/Sydney",
    "US/Eastern": "America/New_York", "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver", "US/Pacific": "America/Los_Angeles",
}
_COORD = re.compile(r"^([+-])(\d{2})(\d{2})(\d{2})?([+-])(\d{3})(\d{2})(\d{2})?$")


def parse_coord(text):
    """ISO 6709 '+DDMM[SS]+DDDMM[SS]' -> (lat, lon) degrees, or None."""
    m = _COORD.match(text)
    if not m:
        return None
    s1, d1, m1, x1, s2, d2, m2, x2 = m.groups()
    lat = int(d1) + int(m1) / 60 + int(x1 or 0) / 3600
    lon = int(d2) + int(m2) / 60 + int(x2 or 0) / 3600
    return (-lat if s1 == "-" else lat, -lon if s2 == "-" else lon)


def parse_tab(text):
    """{zone: (lat, lon)} from zone1970.tab / zone.tab contents."""
    zones = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) >= 3:
            coord = parse_coord(cols[1])
            if coord is not None:
                zones.setdefault(cols[2], coord)
    return zones


def zone_from_path(path):
    """'Europe/Berlin' from '/usr/share/zoneinfo/Europe/Berlin' (or posix/...)."""
    path = path.replace("\\", "/")
    if "zoneinfo/" not in path:
        return None
    zone = path.split("zoneinfo/", 1)[1]
    for prefix in ("posix/", "right/"):
        if zone.startswith(prefix):
            zone = zone[len(prefix):]
    return zone or None


def _tzlocal_name():
    import tzlocal
    return tzlocal.get_localzone_name()


def local_zone(env=None, platform=None, readlink=os.path.realpath, tzlocal_name=None):
    """The IANA zone name: $TZ, else /etc/localtime's target (POSIX), else
    tzlocal (Windows). None if unknown."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    tz = (env.get("TZ") or "").lstrip(":")
    if "/" in tz and not tz.startswith("/"):
        return tz
    if tz.startswith("/"):
        return zone_from_path(tz)
    if platform == "win32":
        try:
            return (tzlocal_name or _tzlocal_name)() or None
        except Exception:
            return None
    try:
        return zone_from_path(readlink("/etc/localtime"))
    except Exception:
        return None


def _tzdata_dir():
    import tzdata
    return os.path.join(os.path.dirname(tzdata.__file__), "zoneinfo")


def tab_candidates(dirs=ZONEINFO_DIRS, tzdata_dir=_tzdata_dir):
    try:
        dirs = (*dirs, tzdata_dir())
    except Exception:
        pass
    return [os.path.join(d, name) for name in TAB_FILES for d in dirs]


class TzLocation:
    """Callable LocationHint. Everything is injectable for tests."""

    def __init__(self, zone=local_zone, candidates=tab_candidates):
        self._zone = zone
        self._candidates = candidates

    def __call__(self):
        try:
            zone = self._zone()
            if not zone:
                return None
            zone = ALIASES.get(zone, zone)
            for path in self._candidates():
                try:
                    with open(path, encoding="utf-8") as f:
                        found = parse_tab(f.read()).get(zone)
                except OSError:
                    continue
                if found is not None:
                    return found
        except Exception:
            pass
        return None
