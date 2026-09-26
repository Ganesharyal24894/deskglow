"""Sunset time for a place and a date: the NOAA solar calculator, as pure maths.

Port of the NOAA Global Monitoring Laboratory solar calculator (the
"calcSunriseSetUTC" routine, itself after Meeus, *Astronomical Algorithms*).
Accurate to about a minute between latitudes +-72 degrees. Longitude is
positive east.
"""
import datetime
import math

ZENITH = 90.833   # refraction + the sun's radius: the "official" sunset


def _julian_day(d):
    """Julian day number at 0h UTC on the calendar date `d`."""
    y, m = d.year, d.month
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d.day + b - 1524.5


def _sun(t):
    """(equation of time in minutes, declination in degrees) at Julian century t."""
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289)
    omega = math.radians(125.04 - 1934.136 * t)
    app_long = l0 + c - 0.00569 - 0.00478 * math.sin(omega)
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    obliq = 23.0 + (26.0 + seconds / 60.0) / 60.0 + 0.00256 * math.cos(omega)
    decl = math.degrees(math.asin(math.sin(math.radians(obliq))
                                  * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obliq) / 2.0) ** 2
    l0r = math.radians(l0)
    eq = (y * math.sin(2 * l0r) - 2 * e * math.sin(mr)
          + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
          - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return math.degrees(eq) * 4.0, decl


def _sunset_minutes(jd, lat, lon):
    """Minutes after 0h UTC of the day whose Julian day is `jd`, or None."""
    t = (jd - 2451545.0) / 36525.0
    eq_time, decl = _sun(t)
    lat_r, dec_r = math.radians(lat), math.radians(decl)
    arg = (math.cos(math.radians(ZENITH)) / (math.cos(lat_r) * math.cos(dec_r))
           - math.tan(lat_r) * math.tan(dec_r))
    if not -1.0 <= arg <= 1.0:
        return None            # midnight sun or polar night: no sunset today
    hour_angle = -math.degrees(math.acos(arg))
    return 720.0 - 4.0 * (lon + hour_angle) - eq_time


def sunset_utc(lat, lon, date):
    """Sunset on local calendar `date` at (lat, lon) as an aware UTC datetime,
    or None when the sun doesn't set (or rise) that day."""
    jd = _julian_day(date)
    first = _sunset_minutes(jd, lat, lon)
    if first is None:
        return None
    # second pass at the approximate time of sunset, as NOAA does
    minutes = _sunset_minutes(jd + first / 1440.0, lat, lon)
    if minutes is None:
        return None
    midnight = datetime.datetime(date.year, date.month, date.day,
                                 tzinfo=datetime.timezone.utc)
    return midnight + datetime.timedelta(minutes=minutes)
