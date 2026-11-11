"""Lutheran church year: find the season for a date."""
import datetime as dt
import re

SEASONS = ["advent", "christmas", "epiphany", "lent", "holyweek", "easter", "pentecost"]

# Patriotic songs are not a church season. They play only on the weekend of these holidays.
PATRIOTIC = "patriotic"
HOLIDAYS = ["memorial", "independence", "veterans"]

# Words in a file name or folder name that mark a song for a season.
SEASON_WORDS = {
    "advent": ["advent"],
    "christmas": ["christmas", "noel", "nativity", "bethlehem", "manger", "silent night"],
    "epiphany": ["epiphany", "magi", "wise men", "transfiguration"],
    "lent": ["lent", "ash wednesday", "lenten"],
    "holyweek": ["holy week", "palm sunday", "maundy", "good friday", "passion", "calvary"],
    "easter": ["easter", "resurrection", "risen", "alleluia"],
    "pentecost": ["pentecost", "holy spirit", "trinity"],
    PATRIOTIC: ["patriotic", "america", "american", "god bless america", "star spangled",
                "battle hymn", "my country", "eternal father", "memorial day", "veterans",
                "july 4", "fourth of july"],
}


def easter(year):
    """Western Easter Sunday (Anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def advent_start(year):
    """First Sunday of Advent: the fourth Sunday before Christmas Day."""
    xmas = dt.date(year, 12, 25)
    days_back = (xmas.weekday() + 1) % 7 or 7  # last Sunday before Dec 25
    return xmas - dt.timedelta(days=days_back + 21)


def season(date):
    """Return the season name for a date."""
    y = date.year
    if date >= advent_start(y) and date < dt.date(y, 12, 25):
        return "advent"
    if date >= dt.date(y, 12, 25) or date <= dt.date(y, 1, 5):
        return "christmas"
    e = easter(y)
    ash_wed = e - dt.timedelta(days=46)
    palm_sun = e - dt.timedelta(days=7)
    pentecost_day = e + dt.timedelta(days=49)
    if date < ash_wed:
        return "epiphany"
    if date < palm_sun:
        return "lent"
    if date < e:
        return "holyweek"
    if date < pentecost_day:
        return "easter"
    return "pentecost"  # Pentecost Day and the time after Pentecost


def holiday_date(name, year):
    """Date of a patriotic holiday."""
    if name == "memorial":  # last Monday in May
        d = dt.date(year, 5, 31)
        return d - dt.timedelta(days=d.weekday())
    if name == "independence":
        return dt.date(year, 7, 4)
    if name == "veterans":
        return dt.date(year, 11, 11)
    if name == "labor":  # first Monday in September
        d = dt.date(year, 9, 1)
        return d + dt.timedelta(days=(7 - d.weekday()) % 7)
    raise ValueError(f"Unknown holiday: {name}")


def patriotic_holiday(date, holidays=HOLIDAYS):
    """Name of the patriotic holiday whose weekend this date is in, else None.
    The weekend is the Sunday nearest the holiday (3 days before to 3 days after)."""
    wd = date.weekday()  # Mon=0 .. Sun=6; Mon-Wed belong to the Sunday before
    sunday = date - dt.timedelta(days=wd + 1) if wd < 3 else date + dt.timedelta(days=6 - wd)
    for name in holidays:
        if abs((holiday_date(name, sunday.year) - sunday).days) <= 3:
            return name
    return None


def allowed_seasons(name):
    """Song seasons that may play in a church season.
    Holy Week may also use Lent songs."""
    return {"holyweek": {"holyweek", "lent"}}.get(name, {name})


def date_from_filename(name):
    """Get the service date from names like 'BLCTrad10.11.2026 08-10.mkv' (MM.DD.YYYY)."""
    m = re.search(r"(\d{1,2})[.\-_](\d{1,2})[.\-_](\d{4})", name)
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", name)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def default_service_date(today=None):
    """The coming Sunday, or today when today is a Sunday."""
    today = today or dt.date.today()
    return today + dt.timedelta(days=(6 - today.weekday()) % 7)


def service_date(shown, picked, filename, today=None):
    """The date to build for: the date the person picked in the calendar, else the date in the
    file name, else the coming Sunday (today, on a Sunday)."""
    if picked:
        return shown
    return date_from_filename(filename) or default_service_date(today)


def guess_seasons(text):
    """Guess song seasons from a file path. Empty set means 'general' (any time)."""
    t = re.sub(r"[_\-.]+", " ", text.lower())
    return {s for s, words in SEASON_WORDS.items()
            if any(re.search(rf"\b{re.escape(w)}\b", t) for w in words)}
