"""Accepted episode extensions must not become catalogue schema requirements."""
import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_catalogue as c
import mettle_work as w
from examples.scalability_fixture import record
from reference_retrieval_031 import retrieve_031


class EpisodeMetadataTest(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self, **extra):
        with tempfile.TemporaryDirectory(prefix="mettle-episode-metadata-") as temporary:
            root = Path(temporary).resolve()
            m.install(root, [])
            store = m.Store(root)
            # Exercise the ordinary publication API, including all canonical guards.
            with store.lock():
                store.publish(record("episode", "E-normal", title="Normal observation"), None)
                store.publish(record("lesson", "L-current", domain="fixture", scope=["component"],
                                     origin=["E-normal"], title="Current lessonword"), 0)
                store.publish(record("episode", "E-extra", title="Episodeword component/fallback", **extra), None)
            yield store

    def cli(self, store, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(store.home / "tools/mettle.py"),
                               *args, "--root", str(store.root)],
                              capture_output=True, encoding="utf-8", timeout=90)

    def query(self, store, query, scope=None, kind="lessons"):
        with store.lock():
            return w.retrieve(m, store, query, 5, scope, kind)

    def hashes(self, store):
        records, lessons = store.snapshot()
        paths = [entry[2] for entry in records.values()]
        paths += [entry[2] for versions in lessons.values() for entry in versions]
        paths += list(store.path("personality").glob("*.md"))
        paths.append(store.path("memory/vocabulary.md"))
        return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    def test_null_extras_do_not_block_cold_unrelated_reads_or_lesson_search(self):
        for field in ("scope", "tags", "aliases", "domain"):
            with self.subTest(field=field), self.fixture(**{field: None}) as store:
                before = self.hashes(store)  # Complete canonical validation succeeds.
                self.assertEqual(self.cli(store, "check").returncode, 0)
                expected = retrieve_031(m, store, ["lessonword"], 5, None)
                self.assertEqual([item["id"] for item in expected], ["L-current"])
                self.assertEqual(self.query(store, ["lessonword"]), expected)
                store.path(c.RELATIVE).unlink()  # A fresh process must also rebuild for unrelated show.
                result = self.cli(store, "show", "E-normal")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(m.decode(result.stdout)[0]["id"], "E-normal")
                result = self.cli(store, "show", "E-extra")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNone(m.decode(result.stdout)[0][field])
                self.assertEqual(self.hashes(store), before)

    def test_null_extras_allow_repair_check_and_source_install_without_rewriting_records(self):
        with self.fixture(scope=None, tags=None, aliases=None, domain=None) as store:
            before = self.hashes(store)
            result = self.cli(store, "reindex", "--repair")
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.cli(store, "check")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["catalogue"], "verified against canonical snapshot")
            m.install(store.root, [])
            self.assertEqual(self.query(store, ["episodeword"], "fallback", "episodes")[0]["id"], "E-extra")
            self.assertEqual(self.hashes(store), before)

    def test_other_extension_shapes_are_safe_for_direct_reads_and_scoped_episode_search(self):
        for value in (None, False, 7, {"ignoredkey": "ignoredvalue"}, "opaqueextension",
                      [None, 3, {"nestedkey": "nestedvalue"}, ["nestedtext"], "usefultext"]):
            with self.subTest(value=value), self.fixture(scope=value, tags=value, aliases=value, domain=value) as store:
                before = self.hashes(store)
                with store.lock(), c.open_catalogue(m, store) as catalogue:
                    meta, _, _ = catalogue.get("E-extra")
                    for field in ("scope", "tags", "aliases", "domain"):
                        self.assertEqual(meta[field], value)
                hits = self.query(store, ["episodeword"], "fallback", "episodes")
                self.assertEqual([item["id"] for item in hits], ["E-extra"])
                self.assertEqual(self.query(store, ["episodeword"], "absentscope", "episodes"), [])
                self.assertEqual(self.query(store, ["ignoredkey"], kind="episodes"), [])
                if isinstance(value, list):
                    self.assertEqual(self.query(store, ["usefultext"], "usefultext", "episodes")[0]["id"], "E-extra")
                    self.assertEqual(self.query(store, ["nestedtext"], kind="episodes"), [])
                self.assertEqual(self.hashes(store), before)

    def test_well_formed_optional_text_keeps_031_ranking_and_scope_behavior(self):
        with self.fixture(domain="optional-domain", tags=["uniquetag", "日本"],
                          aliases=["source of truth", "custom_symbol"], scope=["component/special"]) as store:
            before = self.hashes(store)
            for query in (["optional-domain"], ["uniquetag"], ["日本"], ["source", "of", "truth"],
                          ["source"], ["custom_symbol"], ["episodeword"]):
                for scope in (None, "component/special", "fallback", "absent"):
                    with self.subTest(query=query, scope=scope):
                        expected = retrieve_031(m, store, query, 5, scope, "episodes")
                        self.assertEqual(self.query(store, query, scope, "episodes"), expected)
            self.assertEqual(self.hashes(store), before)

    def test_previous_lexical_catalogue_is_rebuilt_and_canonical_hashes_are_preserved(self):
        with self.fixture(tags=["ordinarytag"]) as store:
            before = self.hashes(store)
            with store.lock(), mock.patch.object(c, "LEXICAL_VERSION", "phrases-v1-sequences-1"):
                c.rebuild(m, store, store.snapshot())
            with mock.patch.object(store, "snapshot", wraps=store.snapshot) as snapshots:
                self.assertEqual(self.query(store, ["ordinarytag"], kind="episodes")[0]["id"], "E-extra")
            self.assertEqual(snapshots.call_count, 1)
            with contextlib.closing(sqlite3.connect(store.path(c.RELATIVE))) as db:
                info = json.loads(db.execute("SELECT value FROM info").fetchone()[0])
            self.assertEqual(info["lexical"], c.LEXICAL_VERSION)
            self.assertNotEqual(info["lexical"], "phrases-v1-sequences-1")
            self.assertEqual(self.hashes(store), before)


if __name__ == "__main__":
    unittest.main()
