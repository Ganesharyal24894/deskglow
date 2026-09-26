"""deskglow.model.sun: NOAA sunset times against published values."""
import datetime as dt

import pytest

from deskglow.model.sun import sunset_utc


def utc(*args):
    return dt.datetime(*args, tzinfo=dt.timezone.utc)


# (place, lat, lon, local date, published sunset in UTC) — timeanddate.com/NOAA
KNOWN = [
    ("London midsummer", 51.5074, -0.1278, dt.date(2024, 6, 21), utc(2024, 6, 21, 20, 21)),
    ("New York midwinter", 40.7128, -74.0060, dt.date(2024, 12, 21), utc(2024, 12, 21, 21, 32)),
    ("Delhi new year", 28.6139, 77.2090, dt.date(2024, 1, 1), utc(2024, 1, 1, 12, 6)),
    ("Sydney new year", -33.8688, 151.2093, dt.date(2024, 1, 1), utc(2024, 1, 1, 9, 9)),
    # west of Greenwich the local-evening sunset falls on the next UTC day
    ("Honolulu equinox", 21.3069, -157.8583, dt.date(2024, 3, 20), utc(2024, 3, 21, 4, 42)),
]


@pytest.mark.parametrize("place,lat,lon,day,expected", KNOWN, ids=[k[0] for k in KNOWN])
def test_sunset_matches_published_times_within_two_minutes(place, lat, lon, day, expected):
    got = sunset_utc(lat, lon, day)
    assert abs((got - expected).total_seconds()) <= 120, f"{place}: {got} vs {expected}"


def test_result_is_an_aware_utc_datetime():
    got = sunset_utc(51.5, 0.0, dt.date(2024, 3, 1))
    assert got.tzinfo is not None and got.utcoffset() == dt.timedelta(0)


def test_polar_day_has_no_sunset():
    """Tromsø at midsummer: the sun never sets."""
    assert sunset_utc(69.65, 18.96, dt.date(2024, 6, 21)) is None


def test_polar_night_has_no_sunset_either():
    assert sunset_utc(69.65, 18.96, dt.date(2024, 12, 21)) is None


def test_sunset_moves_later_in_summer_at_northern_latitudes():
    winter = sunset_utc(51.5, 0.0, dt.date(2024, 12, 21))
    summer = sunset_utc(51.5, 0.0, dt.date(2024, 6, 21))
    assert summer.time() > winter.time()
