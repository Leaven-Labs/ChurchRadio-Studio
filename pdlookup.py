"""Is a song in the public domain? A guide for the person choosing songs, not legal advice.

It judges the song (its words and tune), never the recording: a modern recording or arrangement
of a public-domain hymn is still protected.

US rule: a work published in year Y is in the public domain from 1 January of Y + 96
(everything published before 1931 is free in 2026).

Sources, tried in order (SOURCES). Each returns a result or None for "not found":
- Wikidata (free, open data; one query per song through query.wikidata.org).
- The app's own hymn list: it holds lyric lines only for public-domain hymns (offline fallback).
A second online source can be added to SOURCES later without changing the rest.

Result: {"status": "yes" | "allowed" | "no" | "check" | "unknown", "note": text for the person,
         "source": name}
  yes     = public domain.
  allowed = under copyright, but released under a license that lets anyone broadcast it (Creative
            Commons, from Wikidata's "copyright license"). A NonCommercial license gives "check".
            A church's own permission (a streaming or radio license, a letter from the writer) is
            not looked up: the person marks it in the Songs window (catalog column "permission").
  no      = still under copyright.
  check   = the original is old, but a newer version (an English translation, an adaptation) may be
            the one sung; or the match is not certain.
  unknown = not found, or no dates to go on.
"""
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import paths

SPARQL_URL = "https://query.wikidata.org/sparql"
TIMEOUT = 60
PAUSE = 1.0  # seconds between songs, to be polite to Wikidata
STATUS_LABELS = {"yes": "Yes", "allowed": "Allowed", "no": "No", "check": "Check", "unknown": "?"}
CLEARED = ("yes", "allowed")  # statuses that may be broadcast

PUBLIC_DOMAIN = "Q19652"  # Wikidata: public domain
COPYRIGHTED = "Q50423863"  # Wikidata: copyrighted

# Hymn-like items: the class or the description must say so. Recordings, albums, films, episodes
# and pop songs that share the title are left out.
VERSION_WORDS = ("hymn", "carol", "chorale", "psalm", "spiritual", "lyrics", "translat", "adapt",
                 "melody", "tune", "worship song", "christian song", "gospel song", "anthem")
# A song described only as "song written / composed by ..." can be the song itself (a modern worship
# song), but not a newer version of a hymn: "Joy to the World" (1970, Hoyt Axton) is another song.
HYMN_WORDS = VERSION_WORDS + ("song written", "composed")
NOT_WORK_WORDS = ("recording", "track", "album", "single", "audio", "film", "episode", "video",
                  "disambiguation", "book", "print", "painting", "edition")
TRANSLATION_WORDS = ("translat", "english version", "english language version")
# Licenses that let anyone share (and so broadcast) the work. NonCommercial ones only for
# non-commercial use, which a radio station may not be: those are "check".
FREE_LICENSE_WORDS = ("creative commons", "cc0", "cc by", "cc-by")
NON_COMMERCIAL_WORDS = ("noncommercial", "non-commercial", "-nc", " nc ")

QUERY = """SELECT ?item ?num ?label ?desc
  (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases)
  (GROUP_CONCAT(DISTINCT ?classLabel; separator="|") AS ?classes)
  (MIN(?pub) AS ?published) (MIN(?inc) AS ?created)
  (GROUP_CONCAT(DISTINCT STR(?status); separator="|") AS ?statuses)
  (MAX(?creatorDied) AS ?creatorsDied) (MAX(?translatorDied) AS ?translatorsDied)
  (GROUP_CONCAT(DISTINCT ?translatorName; separator="|") AS ?translators)
  (GROUP_CONCAT(DISTINCT ?licenseName; separator="|") AS ?licenses)
WHERE {
  SERVICE wikibase:mwapi { bd:serviceParam wikibase:endpoint "www.wikidata.org"; wikibase:api "EntitySearch";
      mwapi:search "%s"; mwapi:language "en"; mwapi:limit "15".
      ?item wikibase:apiOutputItem mwapi:item. ?num wikibase:apiOrdinal true. }
  OPTIONAL { ?item rdfs:label ?label FILTER(LANG(?label) = "en") }
  OPTIONAL { ?item schema:description ?desc FILTER(LANG(?desc) = "en") }
  OPTIONAL { ?item skos:altLabel ?alias FILTER(LANG(?alias) = "en") }
  OPTIONAL { ?item wdt:P31 ?class . ?class rdfs:label ?classLabel FILTER(LANG(?classLabel) = "en") }
  OPTIONAL { ?item wdt:P577 ?pub } OPTIONAL { ?item wdt:P571 ?inc } OPTIONAL { ?item wdt:P6216 ?status }
  OPTIONAL { ?item wdt:P50|wdt:P86|wdt:P676 ?creator . ?creator wdt:P570 ?creatorDied }
  OPTIONAL { ?item wdt:P655 ?tr . OPTIONAL { ?tr wdt:P570 ?translatorDied }
             OPTIONAL { ?tr rdfs:label ?translatorName FILTER(LANG(?translatorName) = "en") } }
  OPTIONAL { ?item wdt:P275 ?lic . ?lic rdfs:label ?licenseName FILTER(LANG(?licenseName) = "en") }
} GROUP BY ?item ?num ?label ?desc ORDER BY ?num"""


class LookupError_(Exception):
    """The lookup site could not be reached or answered with an error."""


def cutoff_year(today=None):
    """The last publication year that is in the public domain in the US today."""
    return (today or dt.date.today()).year - 96


def norm(title):
    """Title for comparing: lower case, '&' = 'and', no punctuation or extra spaces."""
    t = title.lower().replace("&", " and ").replace("’", "'")
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def short_title(title):
    """The title without a part in brackets or a track number: '03 - Amazing Grace (Live)' ->
    'Amazing Grace'. Empty if there is nothing to take off."""
    t = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", title)
    t = re.sub(r"^\s*\d{1,3}\s*[-._)]\s*", "", t)
    t = " ".join(t.split()).strip(" -")
    return t if t and norm(t) != norm(title) else ""


def _year(text):
    m = re.match(r"\s*(-?\d{1,4})", text or "")
    return int(m.group(1)) if m else None


# ---- Wikidata ---------------------------------------------------------------------------------
def user_agent():
    return f"ChurchRadioStudio/{paths.version()} (https://github.com/Leaven-Labs/ChurchRadio-Studio)"


def _get(url, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(),
                                               "Accept": "application/sparql-results+json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt + 1 < tries:  # busy: wait as asked, then try again
                try:
                    wait = int(e.headers.get("Retry-After") or 5)
                except ValueError:
                    wait = 5
                time.sleep(min(60, max(1, wait)))
                continue
            if e.code in (429, 503):
                raise LookupError_("Wikidata is busy right now. Try again later: the songs "
                                   "already checked are kept.") from e
            raise LookupError_(f"Wikidata answered {e.code} {e.reason}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LookupError_(f"Could not reach Wikidata ({getattr(e, 'reason', e)})") from e
    raise LookupError_("Wikidata is busy right now. Try again later.")


def query(title):
    """Wikidata's raw answer for the title (one query)."""
    safe = " ".join(title.replace("\\", " ").replace('"', " ").split())
    return _get(SPARQL_URL + "?" + urllib.parse.urlencode({"query": QUERY % safe, "format": "json"}))


def wikidata_items(title):
    """Wikidata items found for the title, best match first."""
    return parse(query(title))


def parse(data):
    """The items in a Wikidata answer, as plain dicts."""
    items = []
    for b in data.get("results", {}).get("bindings", []):
        g = lambda k: b.get(k, {}).get("value", "")  # noqa: E731
        items.append({
            "id": g("item").rsplit("/", 1)[-1], "label": g("label"), "desc": g("desc"),
            "aliases": [a for a in g("aliases").split("|") if a],
            "classes": [c for c in g("classes").split("|") if c],
            "published": _year(g("published")), "written": _year(g("created")),
            "statuses": {s.rsplit("/", 1)[-1] for s in g("statuses").split("|") if s},
            "creators_died": _year(g("creatorsDied")),
            "translators": [t for t in g("translators").split("|") if t],
            "translators_died": _year(g("translatorsDied")),
            "licenses": [x for x in g("licenses").split("|") if x],
        })
    return items


def hymn_like(item, words=HYMN_WORDS):
    text = " ".join([item["desc"]] + item["classes"]).lower()
    if any(w in item["desc"].lower() for w in NOT_WORK_WORDS):
        return False
    return any(w in text for w in words)


def is_translation(item):
    text = " ".join([item["desc"]] + item["classes"]).lower()
    return bool(item["translators"]) or any(w in text for w in TRANSLATION_WORDS)


def broadcast_license(item):
    """(license name, non-commercial only) for a license that lets anyone share the work, or None."""
    for name in item.get("licenses") or []:
        low = f" {name.lower()} "
        if any(w in low for w in FREE_LICENSE_WORDS):
            return name, any(w in low for w in NON_COMMERCIAL_WORDS)
    return None


def _allowed(item, verdict):
    """A "no" or "unknown" verdict turned into "allowed" (or "check") when the item has a free license."""
    lic = broadcast_license(item)
    if not lic or verdict["status"] not in ("no", "unknown"):
        return verdict
    name, nc = lic
    if nc:
        return {"status": "check", "source": "Wikidata",
                "note": f"Released under {name}: only for non-commercial use. Check that your broadcast "
                        f"counts as non-commercial ({_name(item)})."}
    return {"status": "allowed", "source": "Wikidata",
            "note": f"Allowed: released under {name}, which lets anyone broadcast it (give the credit it "
                    f"asks for) ({_name(item)})."}


def _when(item, cutoff):
    """(year to judge by, why) for one item, or (None, why) when there is nothing to go on.
    The publication year counts; a work written by a year was published no earlier, so a
    written year after the cutoff also means it is still protected."""
    pub, written = item.get("published"), item.get("written")
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", item.get("desc") or "")
    told = int(m.group(1)) if m else None  # "1719 Christmas hymn by Isaac Watts"
    if told is not None and told < min(y for y in (pub, written, told + 1) if y is not None):
        return told, f"from {told}"
    if pub is not None:
        return pub, (f"written {written}, published {pub}" if written is not None and written < pub
                     else f"published {pub}")
    if written is not None:
        return written, f"written {written}"
    if is_translation(item):
        died = item["translators_died"]
        if died is not None and died <= cutoff:
            return died, f"translator died {died}"
        return None, "an English translation with no date"
    if item["creators_died"] is not None and item["creators_died"] <= cutoff:
        return item["creators_died"], f"writer died {item['creators_died']}"
    return None, "no date"


def _free(item, cutoff):
    """True if this item on its own is in the public domain."""
    if COPYRIGHTED in item["statuses"]:
        return False
    if PUBLIC_DOMAIN in item["statuses"]:
        return True
    year, _why = _when(item, cutoff)
    return year is not None and year <= cutoff


def _name(item):
    return f'"{item["label"]}"' + (f" ({item['desc']})" if item["desc"] else "")


def judge(title, items, today=None):
    """The verdict for a song from the Wikidata items found for its title (see the module help)."""
    cutoff = cutoff_year(today)
    want = norm(title)
    found = [i for i in items if hymn_like(i)
             and (norm(i["label"]) == want or any(norm(a) == want for a in i["aliases"]))]
    if not found:
        return None
    main, others = found[0], found[1:]
    year, why = _when(main, cutoff)
    late = year is not None and year > cutoff
    if late and main["creators_died"] is not None and main["creators_died"] <= cutoff - 50 \
            and COPYRIGHTED not in main["statuses"]:
        # A writer dead for centuries and a recent date: most likely the date of an edition.
        return {"status": "check", "source": "Wikidata",
                "note": f"Wikidata gives {why}, but the writer died in {main['creators_died']}: the date is "
                        f"probably of a newer edition ({_name(main)})."}
    if COPYRIGHTED in main["statuses"] or late:
        return _allowed(main, {"status": "no", "note": f"Under copyright: {why} ({_name(main)}).",
                               "source": "Wikidata"})
    if year is None and PUBLIC_DOMAIN not in main["statuses"]:
        return _allowed(main, {"status": "unknown", "note": f"Found {_name(main)} on Wikidata, but {why}.",
                               "source": "Wikidata"})
    first = f"public domain ({why})" if year is not None else "marked public domain"
    if norm(main["label"]) != want and not any(norm(o["label"]) == want and _free(o, cutoff) for o in others):
        return {"status": "check", "source": "Wikidata",
                "note": f"The original {_name(main)} is {first}, but the words sung under this title may be a "
                        "newer translation. Check the translation."}
    for o in others:
        if not hymn_like(o, VERSION_WORDS) or PUBLIC_DOMAIN in o["statuses"] and COPYRIGHTED not in o["statuses"]:
            continue
        oy, owhy = _when(o, cutoff)
        newer = COPYRIGHTED in o["statuses"] or (oy is not None and oy > cutoff)
        if newer or (oy is None and is_translation(o)):
            return {"status": "check", "source": "Wikidata",
                    "note": f"The original is {first}, but there is a newer version: {owhy} "
                            f"({_name(o)}). Check which one is sung."}
    return {"status": "yes", "note": f"{first[0].upper()}{first[1:]}: {_name(main)}.", "source": "Wikidata"}


def wikidata(title, today=None):
    return judge(title, wikidata_items(title), today)


# ---- the app's hymn list (offline) ------------------------------------------------------------
def hymn_list(title, hymns):
    """The app's own hymn list has lyric lines only for public-domain hymns; the others are
    listed by title only."""
    want = norm(title)
    for h in hymns:
        if norm(h["title"]) == want:
            if h.get("lines"):
                return {"status": "yes", "source": "the app's hymn list",
                        "note": "Public domain, according to the app's hymn list."}
            return {"status": "check", "source": "the app's hymn list",
                    "note": "The app's hymn list has this song as one still under copyright (for example "
                            "a newer translation)."}
    return None


# ---- one song ---------------------------------------------------------------------------------
SOURCES = [wikidata]


def lookup(title, hymns=(), today=None, sources=None):
    """The verdict for one song title. Raises LookupError_ if no online source could be reached
    and the hymn list does not know the song either."""
    title = (title or "").strip()
    if not title:
        return {"status": "unknown", "note": "The song has no title.", "source": ""}
    error = None
    for tries in ([title, short_title(title)] if short_title(title) else [title]):
        for source in (SOURCES if sources is None else sources):
            try:
                r = source(tries, today)
            except LookupError_ as e:
                error = e
                continue
            listed = hymn_list(tries, hymns)
            if r and r["status"] == "unknown" and listed:
                r = {**listed, "note": f"{listed['note']} ({r['note']})"}
            elif r and r["status"] == "yes" and listed and listed["status"] == "check":
                r = {**r, "status": "check", "note": f"{r['note']} {listed['note']}"}
            if r:
                if tries != title and r["status"] in CLEARED:  # matched only a shorter title
                    r = {**r, "status": "check",
                         "note": f'"{tries}" is {r["note"][0].lower()}{r["note"][1:]} The part of the title '
                                 "taken off (in brackets) may mean a newer version."}
                return r
        r = hymn_list(tries, hymns)
        if r:
            return r if tries == title or r["status"] != "yes" else {**r, "status": "check",
                                             "note": f'"{tries}" is in the app\'s public-domain hymn list, '
                                                     "but the rest of the title may mean a newer version."}
    if error:
        raise error
    return {"status": "unknown", "note": "Not found on Wikidata.", "source": ""}
