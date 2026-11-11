import datetime as dt
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Never touch the real user folder (%APPDATA%\ChurchRadio Studio) from the tests.
os.environ["CHURCHRADIO_DATA_DIR"] = tempfile.mkdtemp(prefix="churchradio-test-data-")

import audio  # noqa: E402
import paths  # noqa: E402
import builder  # noqa: E402
import catalog  # noqa: E402
import churchyear as cy  # noqa: E402
import picker  # noqa: E402
import prelude  # noqa: E402

D = dt.date


class ChurchYear(unittest.TestCase):
    def test_easter(self):
        self.assertEqual(cy.easter(2026), D(2026, 4, 5))
        self.assertEqual(cy.easter(2027), D(2027, 3, 28))
        self.assertEqual(cy.easter(2025), D(2025, 4, 20))

    def test_advent_start(self):
        self.assertEqual(cy.advent_start(2026), D(2026, 11, 29))
        self.assertEqual(cy.advent_start(2027), D(2027, 11, 28))
        self.assertEqual(cy.advent_start(2022), D(2022, 11, 27))  # Christmas on Sunday

    def test_seasons(self):
        cases = {
            D(2026, 11, 22): "pentecost", D(2026, 11, 29): "advent", D(2026, 12, 24): "advent",
            D(2026, 12, 25): "christmas", D(2027, 1, 5): "christmas", D(2027, 1, 6): "epiphany",
            D(2027, 2, 9): "epiphany", D(2027, 2, 10): "lent", D(2027, 3, 21): "holyweek",
            D(2027, 3, 28): "easter", D(2027, 5, 16): "pentecost", D(2026, 10, 11): "pentecost",
        }
        for date, want in cases.items():
            self.assertEqual(cy.season(date), want, date)

    def test_date_from_filename(self):
        self.assertEqual(cy.date_from_filename("BLCTrad10.11.2026 08-10.mkv"), D(2026, 10, 11))
        self.assertEqual(cy.date_from_filename("x 2026-12-06.mkv"), D(2026, 12, 6))
        self.assertIsNone(cy.date_from_filename("service.mkv"))

    def test_guess(self):
        self.assertEqual(cy.guess_seasons(r"C:\Church Songs #1\O Come O Come Emmanuel (Advent).mp3"), {"advent"})
        self.assertEqual(cy.guess_seasons("Christmas/Joy to the World.mp3"), {"christmas"})
        self.assertEqual(cy.guess_seasons("A Mighty Fortress.mp3"), set())
        self.assertEqual(cy.guess_seasons("Christmas - Silent Night.mp3"), {"christmas"})
        self.assertEqual(cy.guess_seasons("Lent_Beautiful Savior.mp3"), {"lent"})

    def test_patriotic_weekends(self):
        yes = {
            D(2026, 5, 24): "memorial", D(2026, 5, 25): "memorial",  # Memorial Day is 5/25
            D(2026, 7, 5): "independence",                          # July 4 is a Saturday
            D(2026, 11, 8): "veterans",                             # 11/11 is a Wednesday
            D(2027, 11, 14): "veterans",                            # 11/11 is a Thursday
        }
        for date, want in yes.items():
            self.assertEqual(cy.patriotic_holiday(date), want, date)
        for date in (D(2026, 5, 17), D(2026, 5, 31), D(2026, 11, 15), D(2026, 10, 11)):
            self.assertIsNone(cy.patriotic_holiday(date), date)
        self.assertIsNone(cy.patriotic_holiday(D(2026, 9, 6)))
        self.assertEqual(cy.patriotic_holiday(D(2026, 9, 6), ["labor"]), "labor")


class Catalog(unittest.TestCase):
    def test_filter(self):
        rows = {
            "a": {"file": "a", "duration": "200", "seasons": "advent", "enabled": "yes"},
            "l": {"file": "l", "duration": "200", "seasons": "lent", "enabled": "yes"},
            "g": {"file": "g", "duration": "200", "seasons": "", "enabled": "yes"},
            "off": {"file": "off", "duration": "200", "seasons": "", "enabled": "no"},
        }
        self.assertEqual({s["path"] for s in catalog.songs_for(rows, "advent")}, {"a", "g"})
        self.assertEqual({s["path"] for s in catalog.songs_for(rows, "holyweek")}, {"l", "g"})

    def test_patriotic_only_on_holiday(self):
        rows = {
            "p": {"file": "p", "duration": "200", "seasons": "patriotic", "enabled": "yes"},
            "g": {"file": "g", "duration": "200", "seasons": "", "enabled": "yes"},
        }
        self.assertEqual({s["path"] for s in catalog.songs_for(rows, "pentecost")}, {"g"})
        pool = {s["path"]: s for s in catalog.songs_for(rows, "pentecost", patriotic=True)}
        self.assertEqual(set(pool), {"p", "g"})
        self.assertTrue(pool["p"]["seasonal"])
        self.assertEqual({s["path"] for s in catalog.songs_for(rows, "pentecost")}, {"g"})

    def test_update_keeps_edits(self):
        with tempfile.TemporaryDirectory() as d:
            songs = os.path.join(d, "songs")
            os.makedirs(songs)
            for n in ("Advent Hymn.mp3", "Hymn.mp3", "notes.txt"):
                open(os.path.join(songs, n), "w").close()
            csvp = os.path.join(d, "songs.csv")
            rows = catalog.update(csvp, [songs], lambda f: 180.0, log=lambda m: None)
            self.assertEqual(len(rows), 2)
            hymn = os.path.join(songs, "Hymn.mp3")
            rows[hymn]["seasons"] = "lent"
            catalog.save(csvp, rows)
            rows = catalog.update(csvp, [songs], lambda f: 1 / 0, log=lambda m: None)
            self.assertEqual(rows[hymn]["seasons"], "lent")
            self.assertEqual(rows[hymn]["duration"], "180.0")


class SongWords(unittest.TestCase):
    """Songs with no words (instrumentals) are found once and turned off."""

    def _catalog(self, d):
        files = {}
        for name in ("Sung.mp3", "Organ.mp3", "Kept on.mp3"):
            files[name] = os.path.join(d, name)
            open(files[name], "w").close()
        rows = {f: {"file": f, "title": "", "duration": "200", "seasons": "", "enabled": "yes", "words": ""}
                for f in files.values()}
        rows[files["Kept on.mp3"]]["words"] = "0"  # checked before, turned back on by hand
        return files, rows

    def test_no_words_turned_off_once(self):
        with tempfile.TemporaryDirectory() as d:
            files, rows = self._catalog(d)
            csvp = os.path.join(d, "songs.csv")
            heard = {files["Sung.mp3"]: 40, files["Organ.mp3"]: 2}
            asked = []
            off = catalog.check_words(csvp, rows, lambda f, dur: asked.append(f) or heard[f], log=lambda m: None)
            self.assertEqual([r["file"] for r in off], [files["Organ.mp3"]])
            self.assertEqual(rows[files["Organ.mp3"]]["enabled"], "no")
            self.assertEqual(rows[files["Organ.mp3"]]["words"], "2")
            self.assertEqual(rows[files["Sung.mp3"]]["enabled"], "yes")
            self.assertEqual(rows[files["Kept on.mp3"]]["enabled"], "yes")  # never checked again
            self.assertNotIn(files["Kept on.mp3"], asked)
            saved = catalog.load(csvp)
            self.assertEqual(saved[files["Organ.mp3"]]["enabled"], "no")
            # Turned back on by hand: the next check leaves it on.
            rows[files["Organ.mp3"]]["enabled"] = "yes"
            self.assertEqual(catalog.check_words(csvp, rows, lambda f, dur: 1 / 0, log=lambda m: None), [])
            self.assertEqual(rows[files["Organ.mp3"]]["enabled"], "yes")

    def test_check_error_is_tried_again_later(self):
        with tempfile.TemporaryDirectory() as d:
            files, rows = self._catalog(d)
            lines = []
            catalog.check_words(os.path.join(d, "songs.csv"), rows, lambda f, dur: 1 / 0, log=lines.append)
            self.assertEqual(rows[files["Organ.mp3"]]["words"], "")
            self.assertEqual(rows[files["Organ.mp3"]]["enabled"], "yes")
            self.assertTrue(any("Cannot check words" in l for l in lines))

    def test_count_words_listens_in_three_places(self):
        W = lambda t, p: types.SimpleNamespace(word=t, probability=p)
        seg = types.SimpleNamespace(words=[W(" Amazing", 0.9), W(" grace", 0.8), W(" ...", 0.9), W(" la", 0.1)])
        model = mock.Mock()
        model.transcribe.side_effect = lambda *a, **k: ([seg], None)
        with mock.patch.object(prelude, "_read_audio", return_value=[0.0]) as read, \
                mock.patch.object(prelude, "_get_model", return_value=model):
            self.assertEqual(prelude.count_words("s.mp3", 240.0), 6)  # 2 sure words x 3 places
            self.assertEqual([c.args[1:] for c in read.call_args_list], [(45.0, 30.0), (105.0, 30.0), (165.0, 30.0)])
            read.reset_mock()
            prelude.count_words("short.mp3", 60.0)  # a short song is heard whole
            self.assertEqual([c.args[1:] for c in read.call_args_list], [(0.0, None)])


def _tone(path, parts):
    """Write an MP3 of (kind, seconds) parts: 'tone' or 'quiet' (digital silence)."""
    ff = audio.find_tool("ffmpeg")
    ins, labels = [], []
    for i, (kind, sec) in enumerate(parts):
        src = f"sine=f=440:d={sec}" if kind == "tone" else f"anullsrc=r=44100:cl=mono:d={sec}"
        ins += ["-f", "lavfi", "-i", src]
        labels.append(f"[{i}]")
    import subprocess
    subprocess.run([ff, "-v", "error", "-y"] + ins + ["-filter_complex",
                    "".join(labels) + f"concat=n={len(parts)}:v=0:a=1", path], check=True)


def _has_ffmpeg():
    try:
        audio.find_tool("ffmpeg")
        return True
    except RuntimeError:
        return False


class SongSilence(unittest.TestCase):
    """The silence at the start and end of songs is cut, so there is no gap between parts."""

    def test_edges_from(self):
        both = ("silence_start: 0\nsilence_end: 1.5 | silence_duration: 1.5\n"
                "silence_start: 50.2\nsilence_end: 51\nsilence_start: 118\nsilence_end: 120 | x\n")
        self.assertEqual(audio.edges_from(both, 120.0), (1.5, 2.0))
        no_eof_line = "silence_start: 0\nsilence_end: 1.5\nsilence_start: 117.5\n"  # older ffmpeg
        self.assertEqual(audio.edges_from(no_eof_line, 120.0), (1.5, 2.5))
        self.assertEqual(audio.edges_from("silence_start: 50\nsilence_end: 52\n", 120.0), (0.0, 0.0))
        self.assertEqual(audio.edges_from("", 120.0), (0.0, 0.0))
        self.assertEqual(audio.edges_from("silence_start: 0\n", 120.0), (0.0, 0.0))  # all silent

    def test_songs_for_plays_without_the_silence(self):
        rows = {"s": {"file": "s", "duration": "200", "seasons": "", "enabled": "yes",
                      "start_silence": "1.50", "end_silence": "3.00"},
                "new": {"file": "new", "duration": "100", "seasons": "", "enabled": "yes"}}
        pool = {p["path"]: p for p in catalog.songs_for(rows, "pentecost")}
        self.assertEqual((pool["s"]["duration"], pool["s"]["start"], pool["s"]["end"]), (195.5, 1.5, 197.0))
        self.assertEqual((pool["new"]["duration"], pool["new"]["start"], pool["new"]["end"]), (100.0, 0.0, None))
        raw = {p["path"]: p for p in catalog.songs_for(rows, "pentecost", trim=False)}
        self.assertEqual((raw["s"]["duration"], raw["s"]["start"], raw["s"]["end"]), (200.0, 0.0, None))

    def test_update_measures_silence_once(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "A.mp3"), "w").close()
            p, calls = os.path.join(d, "songs.csv"), []
            edges = lambda f: calls.append(f) or (0.25, 1.0)
            rows = catalog.update(p, [d], lambda f: 100.0, log=lambda m: None, get_edges=edges)
            row = rows[os.path.join(d, "A.mp3")]
            self.assertEqual((row["start_silence"], row["end_silence"]), ("0.25", "1.00"))
            catalog.update(p, [d], lambda f: 100.0, log=lambda m: None, get_edges=edges)
            self.assertEqual(len(calls), 1)

    @unittest.skipUnless(_has_ffmpeg(), "ffmpeg not installed")
    def test_real_files_join_back_to_back(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.mp3"), os.path.join(d, "b.mp3")
            _tone(a, [("quiet", 2), ("tone", 4), ("quiet", 3)])
            _tone(b, [("quiet", 1.5), ("tone", 5), ("quiet", 2)])
            la, ta = audio.edge_silence(a)
            lb, tb = audio.edge_silence(b)
            self.assertAlmostEqual(la, 2.0, delta=0.15)
            self.assertAlmostEqual(ta, 3.0, delta=0.15)
            self.assertAlmostEqual(lb, 1.5, delta=0.15)
            self.assertAlmostEqual(tb, 2.0, delta=0.15)
            out = os.path.join(d, "out.mp3")
            length = audio.join_to_mp3([(a, la, audio.duration(a) - ta), (b, lb, audio.duration(b) - tb)],
                                       out, compression={"enabled": False})
            self.assertAlmostEqual(length, 9.0, delta=0.3)  # 4 s + 5 s, no gaps
            import subprocess
            p = subprocess.run([audio.find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", out, "-af",
                                "silencedetect=noise=-50dB:d=0.3", "-f", "null", "-"], capture_output=True, text=True)
            self.assertNotIn("silence_start", p.stderr)


class CatalogFile(unittest.TestCase):
    def test_excel_friendly_and_reads_windows_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "songs.csv")
            catalog.save(p, {"x": {"file": "x", "title": "Lo, How a Rose E\u2019er Blooming", "enabled": "yes"}})
            with open(p, "rb") as fh:
                self.assertTrue(fh.read().startswith(b"\xef\xbb\xbf"))  # Excel sees UTF-8
            self.assertEqual(catalog.load(p)["x"]["title"], "Lo, How a Rose E\u2019er Blooming")
            with open(p, "w", encoding="cp1252", newline="") as fh:  # as Excel saves it
                fh.write("file,title,duration,seasons,enabled\r\nx,Caf\u00e9 Hymn,10,,no\r\n")
            row = catalog.load(p)["x"]
            self.assertEqual(row["title"], "Caf\u00e9 Hymn")
            self.assertFalse(catalog.is_on(row))

    def test_missing_folder_keeps_its_songs(self):
        with tempfile.TemporaryDirectory() as d:
            here, gone = os.path.join(d, "here"), os.path.join(d, "unplugged")
            os.makedirs(here)
            open(os.path.join(here, "A.mp3"), "w").close()
            p = os.path.join(d, "songs.csv")
            catalog.save(p, {
                os.path.join(gone, "B.mp3"): {"file": os.path.join(gone, "B.mp3"), "title": "Kept", "duration": "9"},
                os.path.join(here, "Old.mp3"): {"file": os.path.join(here, "Old.mp3"), "duration": "9"},
            })
            rows = catalog.update(p, [here, gone], lambda f: 100.0, log=lambda m: None)
            self.assertIn(os.path.join(gone, "B.mp3"), rows)        # folder not reachable: kept
            self.assertNotIn(os.path.join(here, "Old.mp3"), rows)   # folder there, file deleted: removed
            self.assertIn(os.path.join(here, "A.mp3"), rows)


class Picker(unittest.TestCase):
    def songs(self, durs, seasonal=False):
        return [{"path": f"{'s' if seasonal else 'g'}{i}", "duration": d, "seasonal": seasonal}
                for i, d in enumerate(durs)]

    def test_fit(self):
        pool = self.songs([181, 243, 199, 305, 162, 221, 278, 190])
        chosen, total = picker.pick_songs(pool, 700, 30, seed=1)
        self.assertLessEqual(abs(total - 700), 30)

    def test_never_over(self):
        chosen, total = picker.pick_songs(self.songs([400, 500]), 300, 30, seed=1)
        self.assertEqual(chosen, [])

    def test_prefers_seasonal(self):
        pool = self.songs([200, 200, 200]) + self.songs([200, 200, 200], seasonal=True)
        chosen, _ = picker.pick_songs(pool, 600, 30, seed=3)
        self.assertTrue(all(s["seasonal"] for s in chosen))

    def test_avoids_recent(self):
        pool = self.songs([200, 200, 200, 200])
        chosen, _ = picker.pick_songs(pool, 400, 10, seed=2, recent={"g0", "g1"})
        self.assertEqual({s["path"] for s in chosen}, {"g2", "g3"})

    def test_nothing_needed(self):
        self.assertEqual(picker.pick_songs(self.songs([200]), -5), ([], 0.0))


class Overlong(unittest.TestCase):
    def test_fits_no_warning(self):
        self.assertIsNone(builder.overlong_warning(124, 3500))
        self.assertIsNone(builder.overlong_warning(124, 3476 + 30))

    def test_overlong_suggests_audacity(self):
        msg = builder.overlong_warning(124, 3590)  # 3/15/2026: 61:54
        self.assertIn("Audacity", msg)
        self.assertNotIn("service alone", msg)

    def test_service_alone_over(self):
        self.assertIn("service alone", builder.overlong_warning(124, 3700))


class Silence(unittest.TestCase):
    def test_parse_and_ranges(self):
        err = ("[silencedetect] silence_start: 10.0\n[silencedetect] silence_end: 18.0 | silence_duration: 8\n"
               "[silencedetect] silence_start: 30\n[silencedetect] silence_end: 33 | silence_duration: 3\n")
        sil = audio.parse_silences(err)
        self.assertEqual(sil, [(10.0, 18.0), (30.0, 33.0)])
        self.assertEqual(audio.keep_ranges(60, sil, 5), [(0.0, 10.5), (17.5, 60)])


class Compression(unittest.TestCase):
    def test_default_filter(self):
        f = audio.compression_filter()
        self.assertIn("acompressor=threshold=0.125893:ratio=4:", f)  # -18 dB, 4:1
        self.assertIn("makeup=1.9953", f)                             # +6 dB
        self.assertIn("alimiter=limit=0.8913", f)                     # -1 dB
        self.assertIn("level=0", f)                                   # no auto gain

    def test_settings_and_off(self):
        self.assertIn("ratio=3:", audio.compression_filter({"ratio": 3}))
        self.assertEqual(audio.compression_filter({"enabled": False}), "")


class Prelude(unittest.TestCase):
    def test_phrase(self):
        words = [("Look", 1.0), (" Good", 330.0), (" morning,", 330.1), ("good", 400.0), ("morning", 400.2)]
        self.assertEqual(prelude.match_phrase(words, "Good morning"), 330.0)
        self.assertEqual(prelude.match_phrase([("so", 1.0), ("Goodmorning.", 2.0)], "Good morning"), 2.0)
        self.assertIsNone(prelude.match_phrase([("good", 1.0), ("job", 1.2)], "Good morning"))

    def _analyse(self, words, **kw):
        W = lambda t, a, p: types.SimpleNamespace(word=t, start=a, end=a + 0.4, probability=p)
        segs = [types.SimpleNamespace(words=[W(*w) for w in words])]
        model = mock.Mock()
        model.transcribe.return_value = (iter(segs), None)
        lines = []
        with mock.patch.object(prelude, "_read_audio", return_value=[0.0]), \
                mock.patch.object(prelude, "_get_model", return_value=model):
            gm, _, before = prelude.analyse("x.mkv", "Good morning", log=lines.append, **kw)
        return gm, before, [l for l in lines if "heard #" in l], lines

    def test_analyse_skips_unsure_chatter_and_uses_the_pastor(self):
        # 11/1/2026: chatter + bells at 5:09 were heard as "Good morning"; the pastor's is at 5:22.
        gm, before, hits, _ = self._analyse([(" Good", 309.0, 0.5), (" morning", 309.4, 0.5), (" Welcome", 312.0, 0.9),
                                             (" Good", 322.0, 0.95), (" morning", 322.4, 0.95),
                                             (" Later", 900.0, 0.9)])
        self.assertEqual(gm, 322.0)
        self.assertEqual([w[0] for w in before], [" Good", " morning", " Welcome"])
        self.assertEqual(len(hits), 2)
        self.assertIn("#1 at 5:09 (sure 50%, skipped, less than 75% sure)", hits[0])
        self.assertIn("#2 at 5:22 (sure 95%, USED)", hits[1])

    def test_analyse_sure_first_hit_is_used(self):
        gm, _, hits, _ = self._analyse([(" Good", 309.0, 0.9), (" morning", 309.4, 0.9),
                                        (" Good", 322.0, 0.95), (" morning", 322.4, 0.95)])
        self.assertEqual(gm, 309.0)
        self.assertIn("USED", hits[0])
        self.assertIn("not used", hits[1])

    def test_analyse_never_jumps_past_the_skip_window(self):
        # An unsure first hit, then a sure one 10 min later (children's sermon): keep the first.
        gm, _, _, lines = self._analyse([(" Good", 309.0, 0.5), (" morning", 309.4, 0.5),
                                         (" Good", 909.0, 0.95), (" morning", 909.4, 0.95)])
        self.assertEqual(gm, 309.0)
        self.assertTrue(any("used the surest one" in l for l in lines))

    def test_analyse_none_sure_uses_the_surest(self):
        gm, _, _, _ = self._analyse([(" Good", 309.0, 0.4), (" morning", 309.4, 0.4),
                                     (" Good", 322.0, 0.6), (" morning", 322.4, 0.6)])
        self.assertEqual(gm, 322.0)

    def test_analyse_not_found(self):
        gm, before, hits, _ = self._analyse([(" Hello", 10.0, 0.9)])
        self.assertIsNone(gm)
        self.assertEqual(hits, [])

    def test_choose_hit(self):
        self.assertIsNone(prelude.choose_hit([]))
        hits = [(10.0, 11.0, 0.5), (20.0, 21.0, 0.8), (30.0, 31.0, 0.99)]
        self.assertEqual(prelude.choose_hit(hits), hits[1])          # first sure one, not the surest
        self.assertEqual(prelude.choose_hit(hits, min_sure=0.0), hits[0])  # 0 = old rule: first hit
        self.assertEqual(prelude.choose_hit(hits, skip_sec=5), hits[0])   # only the first is near

    def test_model_loaded_line_once(self):
        lines = []
        with mock.patch.object(prelude, "_models", {"m": object()}), \
                mock.patch.object(prelude, "_logged_models", set()), \
                mock.patch.object(prelude, "_model_path", return_value="/p"):
            for _ in range(3):
                prelude._get_model("", "m", log=lines.append)
        self.assertEqual(lines, ["Model m: loaded from /p"])

    def test_organ_cut_at_phrase(self):
        start, _ = prelude.choose_start(330.0, [(300.0, 302.0)], [("amen", 100.0, 0.9)])
        self.assertAlmostEqual(start, 329.7)

    def test_choir_kept(self):
        words = [("hmm", 50.0, 0.9)] + [("la", 205.0 + 113.0 * i / 60, 0.9) for i in range(60)]
        start, note = prelude.choose_start(325.0, [(200.0, 203.0), (320.0, 322.0)], words)
        self.assertAlmostEqual(start, 202.7)
        self.assertIn("Choir", note)

    def test_talk_over_organ_is_not_choir(self):
        # 3/15/2026: people talk near the microphone during the organ prelude (one short burst)
        talk = [("w", 61.5 + 0.5 * i, 0.9) for i in range(40)] + [("w", 284.0 + 0.5 * i, 0.9) for i in range(12)]
        gaps = [(26.7, 30.6), (196.5, 198.6), (199.9, 203.8), (297.4, 303.9), (304.0, 326.5)]
        start, note = prelude.choose_start(342.9, gaps, talk)
        self.assertAlmostEqual(start, 342.6)
        self.assertIn("No choir", note)

    def test_keep_start(self):
        self.assertEqual(prelude.find_start("x.mkv", mode="Keep start")[1], 0.0)

    def test_end_phrase_last_match(self):
        # "Thanks be to God" after a reading, then after "Go in peace, serve the Lord"
        words = [("Thanks", 100.0, 100.3), ("be", 100.3, 100.4), ("to", 100.4, 100.5), ("God.", 100.5, 100.9),
                 ("Lord.", 3400.0, 3400.6), ("Thanks", 3402.0, 3402.3), (" be", 3402.3, 3402.4),
                 (" to", 3402.4, 3402.5), (" God!", 3402.5, 3403.0), ("organ", 3410.0, 3410.5)]
        self.assertEqual(prelude.phrase_matches(words, "Thanks be to God"), [(100.0, 100.9), (3402.0, 3403.0)])
        self.assertEqual(prelude.phrase_matches([("thanks", 1.0, 1.2), ("god", 1.5, 1.8)], "Thanks be to God"), [])
        heard = ["Thank", "be", "to", "God."]
        words = [(w, 10.0 + i, 10.5 + i) for i, w in enumerate(heard)]
        self.assertEqual(prelude.phrase_matches(words, "Thanks be to God"), [(10.0, 13.5)])

    def test_choose_end(self):
        # fallback (old rule): the last "Thanks be to God" after "Serve the Lord"
        thanks = [(100.0, 100.9), (3402.0, 3403.0)]
        serve = [(3399.0, 3400.0)]
        self.assertEqual(prelude._choose_end_old(thanks, serve)[0], 3403.0)
        self.assertEqual(prelude._choose_end_old(thanks[:1], serve)[0], 3400.0 + prelude.ANSWER_SEC)
        self.assertIsNone(prelude._choose_end_old([], [])[0])

    def test_choose_end_first_answer(self):
        # a later "Thanks be to God" heard in the music after the service is not used
        serve = [(4256.0, 4257.0)]
        thanks = [(4257.2, 4259.0), (4286.0, 4287.0)]
        self.assertEqual(prelude._choose_end_old(thanks, serve)[0], 4259.0)

    def test_choose_end_talk_goes_on(self):
        # "Serve the Lord with gladness. The Lord bless you ...": not the dismissal, nothing cut
        serve = [(6406.0, 6407.0)]
        words = [("Serve", 6406.0, 6406.3), ("the", 6406.3, 6406.6), ("Lord", 6406.6, 6407.0),
                 ("with", 6407.1, 6407.4), ("gladness.", 6407.4, 6408.0)]
        self.assertIsNone(prelude._choose_end_old([], serve, words)[0])
        # the pastor stops after "Serve the Lord.": cut a little after it
        self.assertEqual(prelude._choose_end_old([], serve, words[:3])[0], 6407.0 + prelude.ANSWER_SEC)

    def test_choose_end_peace_then_blessing(self):
        # "Go in peace, serve the Lord with gladness. The Lord bless you ...": cut a few seconds after it
        peace = [(6403.0, 6404.0)]
        serve = [(6406.0, 6407.0)]
        words = [("Serve", 6406.0, 6406.3), ("the", 6406.3, 6406.6), ("Lord", 6406.6, 6407.0),
                 ("with", 6407.1, 6407.4), ("gladness.", 6407.4, 6408.0), ("The", 6410.5, 6411.3)]
        self.assertEqual(prelude._choose_end_old([], sorted(peace + serve), words, peace)[0], 6411.3)

    def test_snappy_cut(self):
        words = [("word", 100.0, 100.3), ("long", 100.3, 100.8)]
        self.assertEqual(prelude.snappy_cut(100.5, words), 100.8)   # not in the middle of a word
        self.assertEqual(prelude.snappy_cut(101.0, words), 101.0)   # between words: leave it

    def test_choose_end_and_we_will(self):
        # "Go now in peace" then the congregation's "and we will": cut right after it (not the 5 s rule)
        go = [(3400.0, 3402.0)]
        alt = [(3402.5, 3403.8)]
        words = [("and", 3402.5, 3403.2), ("we", 3403.2, 3403.5), ("will", 3403.5, 3403.8)]
        self.assertEqual(prelude.choose_end(go, words=words, alt=alt)[0], 3403.8 + prelude.END_ALT_PAD)

    def test_choose_end_and_we_will_not_mid_word(self):
        # "and we will" ends on a word; the 0.5 s pad lands inside a later word -> cut at that word's end
        go = [(3400.0, 3402.0)]
        words = [("and", 3402.5, 3403.2), ("we", 3403.2, 3403.5), ("will", 3403.5, 3403.8),
                 ("amen", 3404.0, 3404.6)]
        alt = [(3402.5, 3403.8)]
        cut = prelude.choose_end(go, words=words, alt=alt)[0]
        self.assertGreater(cut, 3403.8 + prelude.END_ALT_PAD)   # moved past the pad point (3404.3)
        self.assertEqual(cut, 3404.6)                            # to the end of the word

    def test_choose_end_go_only(self):
        # "Go now in peace" only (no "and we will"): cut 5 s after it
        go = [(3400.0, 3402.0)]
        self.assertEqual(prelude.choose_end(go)[0], 3402.0 + prelude.END_AFTER_SEC)

    def test_choose_end_thanks_be_to_god_is_the_end(self):
        # "Go now in peace" -> "Thanks be to God" -> "and we will": the congregation's
        # "Thanks be to God" is the real end; the cut is right after it
        go = [(3400.0, 3402.0)]
        thanks = [(3402.5, 3403.9)]
        alt = [(3404.5, 3405.9)]
        cut, note = prelude.choose_end(go, alt=alt, answer=thanks)
        self.assertEqual(cut, 3403.9 + prelude.END_ANSWER_PAD)
        self.assertIn("Thanks be to God", note)

    def test_choose_end_thanks_not_mid_word(self):
        go = [(3400.0, 3402.0)]
        words = [("Thanks", 3402.5, 3402.9), ("be", 3402.9, 3403.1), ("to", 3403.1, 3403.3), ("God", 3403.3, 3403.9),
                 ("and", 3404.2, 3404.8)]
        self.assertEqual(prelude.choose_end(go, words=words, answer=[(3402.5, 3403.9)])[0], 3404.8)

    def test_choose_end_thanks_outside_window_or_before_go_ignored(self):
        # a "Thanks be to God" after a reading, or long after the dismissal, is not the answer
        go = [(3400.0, 3402.0)]
        thanks = [(1000.0, 1001.0), (3402.0 + prelude.END_ANSWER_WINDOW + 5, 3402.0 + prelude.END_ANSWER_WINDOW + 6)]
        alt = [(3402.5, 3403.8)]
        cut, note = prelude.choose_end(go, alt=alt, answer=thanks)
        self.assertEqual(cut, 3403.8 + prelude.END_ALT_PAD)   # falls back to "and we will"
        self.assertIn("not heard", note)
        self.assertEqual(prelude.choose_end(go, answer=thanks)[0], 3402.0 + prelude.END_AFTER_SEC)

    def test_find_end_uses_thanks_and_logs_how_sure(self):
        heard = [(" Go", 3400.0, 3400.3, 0.9), (" now", 3400.3, 3400.6, 0.9), (" in", 3400.6, 3400.8, 0.9),
                 (" peace.", 3400.8, 3401.5, 0.9), (" Thanks", 3402.5, 3402.9, 0.6), (" be", 3402.9, 3403.1, 0.5),
                 (" to", 3403.1, 3403.3, 0.7), (" God.", 3403.3, 3403.9, 0.6), (" and", 3404.5, 3404.9, 0.4),
                 (" we", 3404.9, 3405.2, 0.4), (" will", 3405.2, 3405.9, 0.4)]
        lines = []
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(prelude, "_read_audio", return_value=[0.0]), \
                mock.patch.object(prelude, "_hear_in_pieces", return_value=heard):
            wf = os.path.join(d, "end_words.txt")
            found, end, note = prelude.find_end("x.mkv", 3600.0, words_file=wf, log=lines.append)
            with open(wf, encoding="utf-8") as fh:
                self.assertIn("God.  (sure 60%)", fh.read())
        self.assertEqual(end, 3403.9 + prelude.END_ANSWER_PAD)
        self.assertTrue(any("sure 60%" in l and "1.0 s after" in l for l in lines), lines)
        # answer phrase turned off in config.json: back to "and we will"
        with mock.patch.object(prelude, "_read_audio", return_value=[0.0]), \
                mock.patch.object(prelude, "_hear_in_pieces", return_value=heard):
            self.assertEqual(prelude.find_end("x.mkv", 3600.0, answer_phrase="")[1], 3405.9 + prelude.END_ALT_PAD)

    def test_choose_end_alt_not_after_go_is_ignored(self):
        # "and we will" heard in the sermon (not after "Go now in peace") is ignored: 5 s rule
        go = [(3400.0, 3402.0)]
        alt = [(1000.0, 1001.0)]
        self.assertEqual(prelude.choose_end(go, alt=alt)[0], 3402.0 + prelude.END_AFTER_SEC)

    def test_choose_end_alt_outside_window(self):
        # "and we will" heard more than the window after "Go now in peace" is not the answer
        go = [(3400.0, 3402.0)]
        alt = [(3402.0 + prelude.END_ALT_WINDOW + 5, 3402.0 + prelude.END_ALT_WINDOW + 6)]
        self.assertEqual(prelude.choose_end(go, alt=alt)[0], 3402.0 + prelude.END_AFTER_SEC)

    def test_choose_end_go_not_found_falls_back(self):
        # "Go now in peace" not heard: choose_end falls back to the old "Thanks be to God" rule
        thanks = [(100.0, 100.9), (3402.0, 3403.0)]
        serve = [(3399.0, 3400.0)]
        self.assertEqual(prelude.choose_end([], thanks=thanks, peace=serve)[0], 3403.0)

    def test_choose_end_never_in_middle_of_word(self):
        # the 5 s cut point lands inside a word: it moves to that word's end
        go = [(3400.0, 3402.0)]
        words = [("long", 3406.0, 3407.0), ("word", 3407.0, 3407.8)]
        cut = prelude.choose_end(go, words=words)[0]
        self.assertGreater(cut, 3402.0 + prelude.END_AFTER_SEC)   # moved past the cut point
        self.assertEqual(cut, 3407.8)                              # to the end of the word

    def test_end_point(self):
        self.assertEqual(prelude.end_point(None, 3600.0), 3600.0)
        # new rules: no pad -- the cut is right at the chosen words ("5 s" means 5 s after)
        self.assertAlmostEqual(prelude.end_point(3403.0, 3600.0), 3403.0)
        # the old fallback keeps the 1 s pad
        self.assertAlmostEqual(prelude.end_point(3403.0, 3600.0, pad=prelude.END_PAD_SEC), 3404.0)
        # never after the file end
        self.assertEqual(prelude.end_point(3605.0, 3600.0), 3600.0)
        self.assertEqual(prelude.end_point(3599.5, 3600.0, pad=prelude.END_PAD_SEC), 3600.0)

    def test_no_end_phrase(self):
        self.assertEqual(prelude.find_end("x.mkv", 3600.0, phrase=""), (None, 3600.0, ""))


class Paths(unittest.TestCase):
    """The user's files live in their own folder, never in the (read-only) program folder."""

    def test_data_dir_override_and_windows_default(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CHURCHRADIO_DATA_DIR": os.path.join(d, "mine")}):
                self.assertEqual(paths.data_dir(), os.path.join(d, "mine"))
                self.assertTrue(os.path.isdir(os.path.join(d, "mine")))
            env = {"CHURCHRADIO_DATA_DIR": "", "APPDATA": os.path.join(d, "Roaming")}
            with mock.patch.dict(os.environ, env), mock.patch.object(paths.sys, "platform", "win32"):
                self.assertEqual(paths.data_dir(), os.path.join(d, "Roaming", "ChurchRadio Studio"))

    def test_models_folder_on_windows(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PROGRAMDATA": d}), \
                    mock.patch.object(prelude.platform, "system", return_value="Windows"):
                self.assertEqual(prelude.fixed_models_dir(), os.path.join(d, "ChurchRadio Studio", "models"))

    def test_user_files_go_to_the_data_folder(self):
        with tempfile.TemporaryDirectory() as d:
            prog, data = os.path.join(d, "Program Files"), os.path.join(d, "AppData")
            os.makedirs(prog)
            with open(os.path.join(prog, "config.json"), "w") as fh:
                fh.write('{"intro": "x"}')
            with mock.patch.object(builder, "bundled_dir", return_value=prog), \
                    mock.patch.dict(os.environ, {"CHURCHRADIO_DATA_DIR": data}):
                self.assertEqual(builder.load_config(), {"intro": "x"})
                self.assertEqual(builder.songs_csv(), os.path.join(data, "songs.csv"))
                self.assertTrue(os.path.isfile(os.path.join(data, "config.json")))

    def test_ffmpeg_installed_with_the_app_is_used_first(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "ffmpeg"))
            exe = "ffmpeg" + (".exe" if sys.platform == "win32" else "")
            mine = os.path.join(d, "ffmpeg", exe)
            open(mine, "w").close()
            with mock.patch.object(audio, "_tools", {}), \
                    mock.patch.object(paths, "program_dir", return_value=d), \
                    mock.patch.object(audio.subprocess, "run") as run:
                self.assertEqual(audio.find_tool("ffmpeg"), mine)
                self.assertEqual(audio.find_tool("ffmpeg"), mine)
                self.assertEqual(run.call_count, 1)  # checked once, then remembered


class ModelsFolder(unittest.TestCase):
    """The speech models live in one fixed folder per PC; first run downloads, later runs load offline."""

    def _mk(self, folder, name="base.en"):
        # faster-whisper/huggingface_hub layout: <root>/models--Systran--faster-whisper-<name>/snapshots/<hash>/
        d = os.path.join(folder, f"models--Systran--faster-whisper-{name}", "snapshots", "abc123")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "model.bin"), "w") as f:
            f.write("x")
        with open(os.path.join(d, "config.json"), "w") as f:
            f.write("{}")
        return d

    def test_config_folder_copied_across_once_and_kept(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "cfg")
            model = self._mk(cfg)
            fixed = os.path.join(d, "fixed")  # stand-in for C:\\ProgramData\\... so the real folder is never touched
            with mock.patch.object(prelude, "fixed_models_dir", return_value=fixed), \
                    mock.patch.object(prelude, "_app_base_dir", return_value=os.path.join(d, "app")):
                self.assertEqual(prelude._models_dir(cfg), fixed)
                self.assertTrue(prelude._model_ready(fixed, "base.en"))  # copied across
                self.assertTrue(os.path.isfile(os.path.join(model, "model.bin")))  # source untouched
                # a model already in the fixed folder is never overwritten by a second run
                marker = [os.path.join(r, "model.bin") for r, _d, f in os.walk(fixed) if "model.bin" in f][0]
                with open(marker, "w") as fh:
                    fh.write("changed")
                self.assertEqual(prelude._models_dir(cfg), fixed)
                with open(marker) as fh:
                    self.assertEqual(fh.read(), "changed")

    def test_copy_out_default_logs_only_when_copied(self):
        with tempfile.TemporaryDirectory() as d:
            src, app = os.path.join(d, "bundle"), os.path.join(d, "app")
            os.makedirs(src)
            os.makedirs(app)
            with open(os.path.join(src, "config.json"), "w") as fh:
                fh.write("{}")
            with mock.patch.object(builder, "bundled_dir", return_value=src), \
                    mock.patch.object(builder, "data_dir", return_value=app):
                self.assertTrue(builder.copy_out_default("config.json"))  # first run: copied
                with open(os.path.join(app, "config.json"), "w") as fh:
                    fh.write('{"mine": 1}')
                self.assertEqual(builder.copy_out_default("config.json"), "")  # kept, not reported
                logged = []
                builder.ensure_user_files(log=logged.append)
                self.assertEqual(logged, [])
                with open(os.path.join(app, "config.json")) as fh:
                    self.assertEqual(fh.read(), '{"mine": 1}')

    def test_folder_order_fixed_when_config_missing(self):
        with tempfile.TemporaryDirectory() as d:
            fixed = os.path.join(d, "fixed")  # stand-in for C:\ProgramData\... so the real folder is never touched
            with mock.patch.object(prelude, "fixed_models_dir", return_value=fixed):
                # a non-existent config path falls back to the fixed per-PC folder
                self.assertEqual(prelude._models_dir(os.path.join(d, "nope")), fixed)

    def test_model_ready_detects_model(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "m")
            os.makedirs(folder)
            self.assertFalse(prelude._model_ready(folder, "base.en"))  # nothing there yet
            self._mk(folder)
            self.assertTrue(prelude._model_ready(folder, "base.en"))
            self.assertFalse(prelude._model_ready(folder, "small.en"))  # a different model is not "there"

    def test_present_model_loads_from_disk_no_download(self):
        """Model files present -> load from the discovered path (no download), log says 'loaded from'."""
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "m")
            self._mk(folder)
            fixed = os.path.join(d, "fixed")  # stand-in for C:\\ProgramData\\... so the real folder is never touched
            calls = []

            class FakeWhisper:
                def __init__(self, source, **kw):
                    self.source = source
                    calls.append((source, kw))

            import prelude as P
            P._models = {}
            P._logged_models = set()
            import builtins
            real_import = builtins.__import__
            def fake_import(name, *a, **kw):
                if name == "faster_whisper":
                    mod = type(sys)("faster_whisper")
                    mod.WhisperModel = FakeWhisper
                    return mod
                return real_import(name, *a, **kw)
            builtins.__import__ = fake_import
            try:
                with mock.patch.object(P, "fixed_models_dir", return_value=fixed), \
                        mock.patch.object(P, "_app_base_dir", return_value=os.path.join(d, "app")):
                    P._get_model(folder, "base.en", log=lambda m: calls.append(("LOG", m)))
            finally:
                builtins.__import__ = real_import
            self.assertEqual(len(calls), 2)
            loaded, kw = calls[0]
            self.assertIn("models--Systran--faster-whisper-base.en", loaded)  # the real snapshot path
            self.assertNotIn("download_root", kw)  # loaded from disk: nothing to download
            self.assertIn("loaded from", calls[1][1])

    def test_missing_model_downloads_once(self):
        """Model files missing -> download by name to the folder, log says 'downloading'."""
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "m")
            os.makedirs(folder)
            fixed = os.path.join(d, "fixed")  # stand-in for C:\\ProgramData\\... so the real folder is never touched
            calls = []

            class FakeWhisper:
                def __init__(self, source, **kw):
                    self.source = source
                    calls.append((source, kw))

            import prelude as P
            P._models = {}
            P._logged_models = set()
            import builtins
            real_import = builtins.__import__
            def fake_import(name, *a, **kw):
                if name == "faster_whisper":
                    mod = type(sys)("faster_whisper")
                    mod.WhisperModel = FakeWhisper
                    return mod
                return real_import(name, *a, **kw)
            builtins.__import__ = fake_import
            try:
                with mock.patch.object(P, "fixed_models_dir", return_value=fixed), \
                        mock.patch.object(P, "_app_base_dir", return_value=os.path.join(d, "app")):
                    P._get_model(folder, "base.en", log=lambda m: calls.append(("LOG", m)))
            finally:
                builtins.__import__ = real_import
            src, kw = calls[0]
            self.assertEqual(src, "base.en")  # a model name: faster-whisper downloads it
            self.assertEqual(kw.get("download_root"), fixed)  # into the fixed folder
            self.assertIn("downloading to", calls[1][1])
            self.assertIn("first run only", calls[1][1])


if __name__ == "__main__":
    unittest.main()


try:
    import songs_window  # noqa: E402  (needs tkinter)
except ImportError:  # pragma: no cover
    songs_window = None


@unittest.skipIf(songs_window is None, "tkinter not installed")
class SongsWindowHelpers(unittest.TestCase):
    def test_labels(self):
        r = {"file": os.path.join("x", "1-03 Organ.mp3"), "title": "", "seasons": "holyweek;lent"}
        self.assertEqual(songs_window.title_of(r), "1-03 Organ")
        self.assertEqual(songs_window.seasons_text(r), "Holy Week, Lent")
        self.assertEqual(songs_window.seasons_text({"seasons": ""}), "General")

    def test_show_and_find(self):
        on = {"file": "Amazing Grace.mp3", "title": "", "enabled": "yes", "words": "40"}
        organ = {"file": "1-03.mp3", "title": "Organ piece", "enabled": "no", "words": "1"}
        unchecked = {"file": "New.mp3", "title": "", "enabled": "yes", "words": ""}
        m = songs_window.matches
        self.assertEqual([m(r, "On", "") for r in (on, organ, unchecked)], [True, False, True])
        self.assertEqual([m(r, "Off", "") for r in (on, organ, unchecked)], [False, True, False])
        self.assertEqual([m(r, "No words", "") for r in (on, organ, unchecked)], [False, True, False])
        self.assertTrue(m(organ, "All songs", "ORGAN"))
        self.assertTrue(m(on, "All songs", "grace"))
        self.assertFalse(m(on, "All songs", "organ"))


try:
    import setup_wizard  # noqa: E402  (needs tkinter)
except ImportError:  # pragma: no cover
    setup_wizard = None


@unittest.skipIf(setup_wizard is None, "tkinter not installed")
class SetupWizardModule(unittest.TestCase):
    def test_pages(self):
        self.assertTrue(callable(setup_wizard.SetupWizard.page_welcome))
        self.assertFalse(hasattr(setup_wizard.SetupWizard, "import_old"))


class SaveConfig(unittest.TestCase):
    def test_save_and_output_name(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CHURCHRADIO_DATA_DIR": d}):
            builder.save_config({"broadcast_name": "St. Paul's Radio", "intro": ""})
            with open(os.path.join(d, "config.json"), encoding="utf-8") as fh:
                self.assertIn("St. Paul's Radio", fh.read())
            self.assertFalse(os.path.exists(os.path.join(d, "config.json.tmp")))
        self.assertEqual(builder.output_name({"broadcast_name": "WXYZ"}, D(2026, 11, 15)), "WXYZ 2026-11-15.mp3")
        self.assertEqual(builder.output_name({}, D(2026, 11, 15)), "Church Radio 2026-11-15.mp3")

    def test_build_without_intro_or_song_folders(self):
        if not _has_ffmpeg():
            self.skipTest("ffmpeg not installed")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CHURCHRADIO_DATA_DIR": d}):
            svc = os.path.join(d, "service.wav")
            _tone(svc, [("tone", 3)])
            cfg = {"intro": "", "song_folders": [], "output_folder": d, "target_minutes": 5,
                   "compression": {"enabled": False}, "broadcast_name": "Test"}
            out = builder.build(svc, cfg=cfg, date=D(2026, 11, 15), log=lambda m: None,
                                start_mode="Keep start", cut_end=False)
            self.assertEqual(os.path.basename(out), "Test 2026-11-15.mp3")
            self.assertAlmostEqual(audio.duration(out), 3.0, delta=0.3)


import identify  # noqa: E402

HYMNS = identify.load_hymns(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hymns.csv"))


class Identify(unittest.TestCase):
    def test_hymn_list_loads_and_seasons_are_known(self):
        self.assertGreater(len(HYMNS), 100)
        known = set(cy.SEASONS) | {cy.PATRIOTIC}
        for h in HYMNS:
            self.assertTrue(set(h["seasons"]) <= known, h["title"])
            self.assertTrue(h["lines"] or len(h["title_tokens"]) >= 2, h["title"])

    def test_lyrics_match_even_when_misheard(self):
        filler = " ".join(["the lord is good and his mercy endures forever"] * 20)
        for heard, want in [("a mazing grays how sweet the sound that saved a wretch like me", "Amazing Grace"),
                            ("silent night holy night all his calm all is bright", "Silent Night"),
                            ("o beautiful for spacious skies for amber waves of grain", "America the Beautiful"),
                            ("and he will raise you up on eagles wings bear you on the breath of dawn", "On Eagle's Wings")]:
            h, sure, _ = identify.match_hymn(filler + " " + heard + " " + filler, HYMNS)
            self.assertEqual(h and h["title"], want)
            self.assertGreaterEqual(sure, identify.LINE_MIN)
        self.assertIsNone(identify.match_hymn(filler + " we will walk in the light together", HYMNS)[0])

    def test_title_only_songs_match_when_the_title_is_sung(self):
        # songs still under copyright are listed by title only: the sung title still finds them
        byt = {h["title"]: h for h in HYMNS}
        self.assertEqual(byt["Here I Am Lord"]["lines"], [])
        h, sure, _ = identify.match_hymn("and here i am lord is it i lord i have heard you calling", HYMNS)
        self.assertEqual(h and h["title"], "Here I Am Lord")
        self.assertIsNone(identify.match_hymn("he lives within my heart and soul", HYMNS)[0])  # too short a title

    def test_title_priority_and_seasons(self):
        heard = "o come o come emmanuel and ransom captive israel"
        r = identify.identify("x/Track 07.mp3", HYMNS, {"title": "Track 07"}, heard)
        self.assertEqual((r["title"], r["seasons"], r["hymn"]), ("O Come O Come Emmanuel", ["advent"], "O Come O Come Emmanuel"))
        self.assertIn("lyrics", r["how"])
        r = identify.identify("x/03.mp3", HYMNS, {"title": "O Come, O Come, Emmanuel"}, heard)
        self.assertEqual(r["title"], "O Come, O Come, Emmanuel")   # good tags are kept
        self.assertIn("tags in the file + lyrics", r["how"])
        r = identify.identify("x/1-07 Christmas Medley.mp3", HYMNS, {}, "la la la")
        self.assertEqual((r["title"], r["seasons"], r["how"]), ("Christmas Medley", ["christmas"], "file name"))
        r = identify.identify("x/a.mp3", HYMNS, {}, heard, known_title="My own title")
        self.assertEqual(r["title"], "My own title")

    def test_file_names_and_generic_tags(self):
        self.assertEqual(identify.title_from_filename("1-03_Amazing_Grace (live).mp3"), "Amazing Grace (live)")
        self.assertEqual(identify.title_from_filename("03 - Holy Night.mp3"), "Holy Night")
        self.assertEqual([t for t in ("Track 03", "Audio 1", "Untitled", "07", "Amazing Grace")
                          if identify.useful_title(t)], ["Amazing Grace"])

    def test_church_hymns_add_and_replace(self):
        with tempfile.TemporaryDirectory() as d:
            mine = os.path.join(d, "hymns.csv")
            with open(mine, "w", encoding="utf-8") as fh:
                fh.write("title,first_line,also,seasons\nOur Parish Song,We gather on the prairie wide,,\n"
                         "Silent Night,Silent night holy night,,advent\n")
            hymns = identify.load_hymns(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hymns.csv"), mine)
            byt = {h["title"]: h for h in hymns}
            self.assertIn("Our Parish Song", byt)
            self.assertEqual(byt["Silent Night"]["seasons"], ["advent"])

    @unittest.skipUnless(_has_ffmpeg(), "ffmpeg not installed")
    def test_read_tags(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.mp3")
            import subprocess
            subprocess.run([audio.find_tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1",
                            "-metadata", "title=Beautiful Savior", "-metadata", "artist=Bethany Choir", p], check=True)
            self.assertEqual(identify.read_tags(p), {"title": "Beautiful Savior", "artist": "Bethany Choir"})


try:
    import add_songs  # noqa: E402  (needs tkinter)
except ImportError:  # pragma: no cover
    add_songs = None


@unittest.skipIf(add_songs is None, "tkinter not installed")
class AddSongsHelpers(unittest.TestCase):
    def test_unique_path(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(add_songs.unique_path(d, "a.mp3"), os.path.join(d, "a.mp3"))
            open(os.path.join(d, "a.mp3"), "w").close()
            self.assertEqual(add_songs.unique_path(d, "a.mp3"), os.path.join(d, "a (2).mp3"))

    def test_analyse_turns_off_songs_without_words(self):
        with mock.patch.object(add_songs.audio, "duration", return_value=200.0), \
                mock.patch.object(add_songs.identify, "read_tags", return_value={}), \
                mock.patch.object(add_songs.identify, "heard_words", return_value=("", 1)), \
                mock.patch.object(add_songs.prelude, "count_words", return_value=2):
            r = add_songs.analyse("x/1-03 Organ Piece.mp3", HYMNS, get_edges=lambda f: (1.0, 2.0))
        self.assertTrue(r["no_words"])
        self.assertEqual((r["title"], r["words"], r["lead"], r["tail"]), ("Organ Piece", 2, 1.0, 2.0))
        with mock.patch.object(add_songs.audio, "duration", return_value=200.0), \
                mock.patch.object(add_songs.identify, "read_tags", return_value={}), \
                mock.patch.object(add_songs.identify, "heard_words",
                                  return_value=("amazing grace how sweet the sound that saved a wretch like me", 12)), \
                mock.patch.object(add_songs.prelude, "count_words") as cw:
            r = add_songs.analyse("x/song.mp3", HYMNS)
        self.assertFalse(r["no_words"])
        self.assertEqual(r["title"], "Amazing Grace")
        cw.assert_not_called()  # enough words heard already: no second listen


class ServiceDate(unittest.TestCase):
    def test_default_is_the_coming_sunday(self):
        self.assertEqual(cy.default_service_date(D(2026, 11, 11)), D(2026, 11, 15))  # Wednesday
        self.assertEqual(cy.default_service_date(D(2026, 11, 14)), D(2026, 11, 15))  # Saturday
        self.assertEqual(cy.default_service_date(D(2026, 11, 15)), D(2026, 11, 15))  # Sunday: today
        self.assertEqual(cy.default_service_date(D(2026, 11, 16)), D(2026, 11, 22))  # Monday
        self.assertEqual(cy.default_service_date(D(2026, 12, 31)), D(2027, 1, 3))   # over the new year

    def test_which_date_is_used(self):
        shown, today = D(2026, 11, 15), D(2026, 11, 11)
        # Picked in the calendar: always that date.
        self.assertEqual(cy.service_date(D(2026, 11, 8), True, "BLC10.11.2026.mkv", today), D(2026, 11, 8))
        # Not picked: the date in the file name, else the coming Sunday.
        self.assertEqual(cy.service_date(shown, False, "BLC10.11.2026.mkv", today), D(2026, 10, 11))
        self.assertEqual(cy.service_date(D(2026, 10, 11), False, "service.mkv", today), D(2026, 11, 15))


try:
    import datepicker  # noqa: E402  (needs tkinter)
except ImportError:
    datepicker = None


@unittest.skipIf(datepicker is None, "tkinter not installed")
class Calendar(unittest.TestCase):
    def test_month_grid_starts_on_sunday(self):
        weeks = datepicker.month_weeks(2026, 11)  # 1 November 2026 is a Sunday
        self.assertEqual(weeks[0][0], D(2026, 11, 1))
        self.assertTrue(all(len(w) == 7 for w in weeks))
        self.assertEqual([d for w in weeks for d in w if d][-1], D(2026, 11, 30))
        self.assertEqual(datepicker.month_weeks(2026, 12)[0][:2], [None, None])  # 1 Dec is a Tuesday
        self.assertEqual(datepicker.add_months(D(2026, 12, 20), 1), D(2027, 1, 1))
        self.assertEqual(datepicker.add_months(D(2026, 1, 31), -1), D(2025, 12, 1))


class ImportSongList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.songs = os.path.join(self.d, "songs")
        os.makedirs(os.path.join(self.songs, "Christmas"))
        for n in ("Hymn.mp3", os.path.join("Christmas", "Joy.mp3"), "Old.mp3"):
            open(os.path.join(self.songs, n), "w").close()
        self.csv = os.path.join(self.d, "songs.csv")
        old = os.path.join(self.songs, "Old.mp3")
        catalog.save(self.csv, {old: {"file": old, "title": "Old Title", "duration": "100", "seasons": "lent",
                                      "enabled": "yes", "words": "40"}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, encoding="utf-8"):
        p = os.path.join(self.d, "import.csv")
        with open(p, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
        return p

    def test_template_imports_its_own_columns(self):
        p = os.path.join(self.d, "template.csv")
        catalog.write_template(p)
        fields, rows = catalog._read_any(p)
        self.assertEqual(fields, catalog.IMPORT_FIELDS)
        self.assertEqual(len(rows), len(catalog.TEMPLATE_ROWS))
        for r in rows:
            catalog.parse_seasons(r["seasons"])  # the examples use valid season words

    def test_seasons(self):
        self.assertEqual(catalog.parse_seasons("Advent; Christmas"), "advent;christmas")
        self.assertEqual(catalog.parse_seasons("lent, Holy Week"), "lent;holyweek")
        self.assertEqual(catalog.parse_seasons("General"), "")
        self.assertEqual(catalog.parse_seasons("Patriotic"), "patriotic")
        with self.assertRaises(ValueError):
            catalog.parse_seasons("summer")

    def test_import_adds_updates_and_reports(self):
        full = os.path.join(self.songs, "Hymn.mp3")
        p = self.write("File,Title,Seasons,Enabled\n"
                       f"{full},A Mighty Fortress,,yes\n"
                       "Joy.mp3,Joy to the World,,\n"     # name only: found in a sub folder
                       "Old.mp3,,Easter,no\n"              # empty title keeps the old one
                       ",,,\n"                             # empty line: ignored
                       "Missing.mp3,Nope,,\n"
                       "Hymn.mp3,Bad,summer,\n"
                       "Hymn.mp3,Bad,,maybe\n")
        rows, added, updated, problems = catalog.import_csv(self.csv, p, [self.songs], lambda f: 200.0,
                                                            get_edges=lambda f: (0.5, 1.0), log=lambda m: None)
        self.assertEqual((added, updated), (2, 1))
        self.assertEqual(len(problems), 3)
        self.assertIn("Line 6", problems[0])
        self.assertIn("summer", problems[1])
        self.assertIn("maybe", problems[2])
        joy = os.path.join(self.songs, "Christmas", "Joy.mp3")
        self.assertEqual(rows[full]["title"], "A Mighty Fortress")
        self.assertEqual(rows[full]["duration"], "200.0")
        self.assertEqual(rows[full]["start_silence"], "0.50")
        self.assertEqual(rows[joy]["seasons"], "christmas")  # guessed from the folder name
        old = rows[os.path.join(self.songs, "Old.mp3")]
        self.assertEqual((old["title"], old["seasons"], old["enabled"], old["duration"]),
                         ("Old Title", "easter", "no", "100"))
        self.assertEqual(catalog.load(self.csv)[joy]["title"], "Joy to the World")  # saved

    def test_excel_windows_encoding_and_no_file_column(self):
        p = self.write("file,title\nHymn.mp3,Café Hymn\n", encoding="cp1252")
        rows, added, _u, problems = catalog.import_csv(self.csv, p, [self.songs], lambda f: 1.0, log=lambda m: None)
        self.assertEqual((added, problems), (1, []))
        self.assertEqual(rows[os.path.join(self.songs, "Hymn.mp3")]["title"], "Café Hymn")
        with self.assertRaises(ValueError):
            catalog.import_csv(self.csv, self.write("title\nX\n"), [self.songs], lambda f: 1.0)


def _item(label, desc="Christian hymn", published=None, written=None, classes=("musical work/composition",),
          aliases=(), statuses=(), creators_died=None, translators=(), translators_died=None):
    return {"id": "Q1", "label": label, "desc": desc, "aliases": list(aliases), "classes": list(classes),
            "published": published, "written": written, "statuses": set(statuses),
            "creators_died": creators_died, "translators": list(translators), "translators_died": translators_died}


class PublicDomain(unittest.TestCase):
    TODAY = D(2026, 11, 11)

    def setUp(self):
        import pdlookup
        self.pd = pdlookup

    def test_cutoff_moves_each_january(self):
        self.assertEqual(self.pd.cutoff_year(D(2026, 11, 11)), 1930)
        self.assertEqual(self.pd.cutoff_year(D(2027, 1, 1)), 1931)

    def test_titles(self):
        self.assertEqual(self.pd.norm("Holy, Holy, Holy!"), "holy holy holy")
        self.assertEqual(self.pd.norm("Faith & Hope"), "faith and hope")
        self.assertEqual(self.pd.short_title("03 - Amazing Grace (Live)"), "Amazing Grace")
        self.assertEqual(self.pd.short_title("Amazing Grace [My Chains Are Gone]"), "Amazing Grace")
        self.assertEqual(self.pd.short_title("Amazing Grace"), "")

    def judge(self, title, items):
        return self.pd.judge(title, items, self.TODAY)

    def test_old_hymn_is_public_domain(self):
        r = self.judge("Amazing Grace", [
            _item("Amazing Grace", written=1772, published=1779),
            _item("Amazing Grace", desc="vocal track by Judy Collins; 1970 studio recording", classes=["music track"]),
            _item("Amazing Grace", desc="2020 song by DaBaby", published=2020),   # not a hymn: left out
            _item("Amazing Grace", desc="2006 film by Michael Apted", published=2006, classes=["film"]),
        ])
        self.assertEqual(r["status"], "yes")
        self.assertIn("published 1779", r["note"])

    def test_new_song_is_under_copyright(self):
        r = self.judge("In Christ Alone", [
            _item("In Christ Alone", desc="Christian song written by Keith Getty and Stuart Townend", published=2001),
            _item("In Christ Alone", desc="Christian hymn text", classes=["lyrics"]),
        ])
        self.assertEqual(r["status"], "no")
        self.assertIn("2001", r["note"])

    def test_newer_english_version_needs_checking(self):
        r = self.judge("How Great Thou Art", [
            _item("How Great Thou Art", published=1885, aliases=["O store Gud"], creators_died=1940),
            _item("How Great Thou Art", desc="1967 studio album by Elvis Presley", published=1966, classes=["album"]),
            _item("How Great Thou Art", desc="translated Christian hymn; English language version",
                  classes=["translated song"]),
            _item("How Great Thou Art", desc="Swedish folk melody as adapted by Stuart K. Hine", published=1949),
        ])
        self.assertEqual(r["status"], "check")

    def test_old_translation_by_a_translator_long_dead(self):
        r = self.judge("Silent Night", [
            _item("Silent Night", desc='translated song; English version of "Stille Nacht"', creators_died=1863,
                  translators=["John Freeman Young"], translators_died=1885),
            _item("Silent Night", desc="vocal track by Rod Stewart; 2012 studio recording", classes=["track"]),
            _item("Stille Nacht Heilige Nacht", desc="Christmas carol", aliases=["Silent Night"], published=1815),
        ])
        self.assertEqual(r["status"], "yes")
        self.assertIn("translator died 1885", r["note"])

    def test_marked_and_unknown(self):
        self.assertEqual(self.judge("Old Hymn", [_item("Old Hymn", statuses=["Q19652"])])["status"], "yes")
        # An undated translation that is marked public domain is no reason to check.
        self.assertEqual(self.judge("Old Hymn", [
            _item("Old Hymn", published=1529),
            _item("Old Hymn", classes=["edition of a translation"], statuses=["Q19652"])])["status"], "yes")
        self.assertEqual(self.judge("Old Hymn", [_item("Old Hymn", statuses=["Q50423863"])])["status"], "no")
        self.assertEqual(self.judge("Old Hymn", [_item("Old Hymn")])["status"], "unknown")
        self.assertEqual(self.judge("Old Hymn", [_item("Old Hymn", creators_died=1850)])["status"], "yes")
        self.assertIsNone(self.judge("Old Hymn", [_item("Other Hymn", published=1800)]))
        self.assertIsNone(self.judge("Old Hymn", []))
        # Written after the cutoff: it cannot have been published before it.
        self.assertEqual(self.judge("New", [_item("New", written=1990)])["status"], "no")

    def test_lookup_order_and_fallbacks(self):
        old = lambda t, today=None: {"status": "yes", "note": "Public domain (published 1779).", "source": "x"} \
            if t == "Amazing Grace" else None
        r = self.pd.lookup("Amazing Grace (My Chains Are Gone)", sources=[old], today=self.TODAY)
        self.assertEqual(r["status"], "check")  # matched only without the part in brackets
        self.assertEqual(self.pd.lookup("Amazing Grace", sources=[old])["status"], "yes")
        self.assertEqual(self.pd.lookup("Nothing", sources=[old])["status"], "unknown")
        self.assertEqual(self.pd.lookup("  ", sources=[old])["status"], "unknown")

        def offline(t, today=None):
            raise self.pd.LookupError_("Could not reach Wikidata")
        hymns = [{"title": "Abide with Me", "lines": [["abide"]]}, {"title": "New Song", "lines": []}]
        self.assertEqual(self.pd.lookup("Abide With Me", hymns, sources=[offline])["status"], "yes")
        # Listed by title only: the app's list has it as still under copyright.
        self.assertEqual(self.pd.lookup("New Song", hymns, sources=[offline])["status"], "check")
        with self.assertRaises(self.pd.LookupError_):  # offline and not in the hymn list: tell the person
            self.pd.lookup("Unknown Song", hymns, sources=[offline])
        # Online: a "?" from Wikidata is answered by the hymn list, and a title-only entry turns Yes into Check.
        unknown = lambda t, today=None: {"status": "unknown", "note": "No date.", "source": "Wikidata"}
        self.assertEqual(self.pd.lookup("Abide with Me", hymns, sources=[unknown])["status"], "yes")
        self.assertEqual(self.pd.lookup("New Song", hymns, sources=[lambda t, today=None: {
            "status": "yes", "note": "Public domain (published 1812).", "source": "Wikidata"}])["status"], "check")

    def test_real_wikidata_answers(self):
        """Answers saved from Wikidata in November 2026, judged as on 11 November 2026."""
        with open(os.path.join(os.path.dirname(__file__), "wikidata_answers.json"), encoding="utf-8") as fh:
            answers = json.load(fh)
        want = {
            "Amazing Grace": "yes", "A Mighty Fortress Is Our God": "yes", "Silent Night": "yes",
            "Holy, Holy, Holy": "yes", "Great Is Thy Faithfulness": "yes", "Lift High the Cross": "yes",
            "Joy to the World": "yes",            # not the 1970 Hoyt Axton song of the same name
            "O Come O Come Emmanuel": "yes", "Abide with Me": "yes", "It Is Well with My Soul": "yes",
            "How Great Thou Art": "check",        # 1885 Swedish original, English version later
            "Prepare the Royal Highway": "check",  # matched only the 1812 Swedish original
            "In Christ Alone": "no", "Shout to the Lord": "no", "Here I Am to Worship": "no",
            "Be Thou My Vision": "unknown", "10,000 Reasons": None, "Track 03": None,
        }
        for title, status in want.items():
            r = self.judge(title, self.pd.parse(answers[title]))
            self.assertEqual(r and r["status"], status, title)

    def test_parse_and_query_text(self):
        data = {"results": {"bindings": [{
            "item": {"value": "http://www.wikidata.org/entity/Q210211"}, "label": {"value": "Amazing Grace"},
            "desc": {"value": "Christian hymn"}, "aliases": {"value": ""}, "classes": {"value": "musical work/composition"},
            "published": {"value": "1779-01-01T00:00:00Z"}, "created": {"value": "1772-01-01T00:00:00Z"},
            "statuses": {"value": "http://www.wikidata.org/entity/Q19652"}, "creatorsDied": {"value": "1807-12-21T00:00:00Z"},
        }]}}
        item = self.pd.parse(data)[0]
        self.assertEqual((item["id"], item["published"], item["written"], item["creators_died"]),
                         ("Q210211", 1779, 1772, 1807))
        self.assertEqual(item["statuses"], {"Q19652"})
        with mock.patch.object(self.pd, "_get", return_value={"results": {"bindings": []}}) as get:
            self.pd.wikidata_items('Say "Amen"\\ now')
        url = get.call_args[0][0]
        self.assertIn("query.wikidata.org/sparql", url)
        self.assertNotIn("%22Amen%22", url)  # quotes taken out of the title: no broken query
