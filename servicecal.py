"""Studio's own calendar helpers: which songs suit a season, and which service a file is for.

The church year itself (Easter, the seasons, the patriotic holiday weekends) comes from the
churchyear package (Leaven-Labs/churchyear), shared with ChurchRadio Manager. What stays here is
only Studio's: the words that mark a song for a season, and the service date from a file name.
"""
import datetime as dt
import re

import churchyear

# Patriotic songs are not a church season. They play only on the weekend of these holidays.
PATRIOTIC = "patriotic"

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
    return churchyear.next_sunday(today or dt.date.today())


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
