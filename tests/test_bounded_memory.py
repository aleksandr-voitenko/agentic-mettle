"""Synthetic scalability contracts: bytes, operation counts, parity and recovery."""
import copy
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_work as w
import mettle_migrate as migration
from examples.scalability_fixture import CountingRecords, old_indexes, put, record, seed
from reference_retrieval import retrieve_reference


class BoundedMemoryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-scale-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"

    def cli(self, *args, source=False):
        helper = Path(m.__file__) if source else self.helper
        return subprocess.run([sys.executable, "-X", "utf8", str(helper), *args,
                               "--root", str(self.root)], capture_output=True, encoding="utf-8", timeout=90)

    def check(self):
        result = self.cli("check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def derived(self):
        return {p: (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.store.path("memory").rglob("*.md") if p.name in {"current.md", "INDEX.md"}}

    def publish(self, kind, identifier, **fields):
        text = record(kind, identifier, **fields)
        with self.store.lock():
            return self.store.publish(text, fields.get("revision", 1) - 1 if kind == "lesson" else None)

    def pages(self, lessons, domain=None):
        found, offset = [], 0
        while True:
            page = self.store.navigation(lessons, domain, offset, 100)
            self.assertLessEqual(len(m.navigation_json(page).encode("utf-8")), m.NAVIGATION_BYTES)
            self.assertEqual(page, self.store.navigation(lessons, domain, offset, 100))
            found.extend(page["items"])
            self.assertEqual(page["remaining"], page["total"] - len(found))
            if page["next_offset"] is None:
                self.assertIsNone(page["next_command"])
                return found
            self.assertGreater(page["next_offset"], offset)
            offset = page["next_offset"]
            self.assertIn(f"--offset {offset}", page["next_command"])

    def test_500_lessons_400_more_domains_bytes_pagination_and_bootstrap(self):
        _, lessons = seed(self.store, lessons=500, long_metadata=True)
        for number in range(1, 401):
            put(self.store, record("lesson", f"L-domain-{number:04d}", origin=["E-00000"],
                                   scope=["synthetic"], domain=f"domain-{number:04d}"))
        _, lessons = self.store.snapshot(verify_views=False)
        self.store.reindex(lessons)
        legacy = old_indexes(self.store, lessons)
        root = self.store.path("memory/INDEX.md")
        domain = self.store.path("memory/lessons/domain-0000/INDEX.md")
        self.assertGreater(len(legacy[domain].encode("utf-8")), m.MAX_RECORD)
        self.assertGreater(len(legacy[root]), m.MAX_CONTEXT)
        self.assertLess(root.stat().st_size, 600)
        for path, text in self.store.indexes(lessons).items():
            self.assertLessEqual(path.stat().st_size, m.NAVIGATION_BYTES)
            self.assertEqual(path.read_bytes(), text.encode("utf-8"))
        domains = self.pages(lessons)
        self.assertEqual([r["domain"] for r in domains], [f"domain-{n:04d}" for n in range(401)])
        items = self.pages(lessons, "domain-0000")
        self.assertEqual([r["id"] for r in items], [f"L-{n:05d}" for n in range(500)])
        self.assertEqual(items[0]["preview_truncated"], ["title", "scope", "aliases"])
        self.assertEqual(items[0]["status"], "proposed")
        self.assertGreater(len(lessons["L-00000"][-1][0]["title"]), len(items[0]["title"]))
        first = json.loads(domain.read_text(encoding="utf-8").split("```json\n")[1].split("```")[0])
        result = self.cli(*shlex.split(first["next_command"]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["items"][0]["id"], f"L-{first['next_offset']:05d}")

        # Required profile/protocol content stays complete after archive growth;
        # optional work previews keep their existing adaptive behavior.
        profiles = {"identity.md": "# Identity\n" + "i" * 3500 + "\n",
                    "dispositions.md": "# Dispositions\n" + "d" * 4500 + "\n"}
        with self.store.lock():
            for number in range(5):
                identifier = w.start(m, self.store, f"Synthetic {number}", "fixture")["id"]
                w.update(m, self.store, identifier, None, "n" * 240, summary_text="s" * 240)
        plan = m.install(self.root, [], profiles=profiles, replace_profiles=True, dry_run=True)
        self.assertLessEqual(plan["startup_characters"] + 256, m.MAX_CONTEXT)
        m.install(self.root, [], profiles=profiles, replace_profiles=True, expected_plan=plan["plan_id"])
        result = self.cli("bootstrap")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout), m.MAX_CONTEXT)
        self.assertGreater(len(result.stdout), m.MAX_CONTEXT - 2000)
        data = json.loads(result.stdout.rstrip().rsplit("\n\n", 1)[1])
        for name, text in profiles.items():
            self.assertEqual(data["profiles"][name]["content"], text)
        self.assertTrue(result.stdout.startswith(m.read(self.store.home / "PERSONALITY.md")))
        self.assertIn("navigate", data["directory_map"])
        self.assertNotIn("domain-0000", data["directory_map"])
        self.assertLess(len(data["unfinished_work"]["items"]), 5)
        self.assertEqual(data["unfinished_work"]["total"], 5)
        self.check()

    def test_single_long_unicode_entry_and_empty_invalid_navigation(self):
        seed(self.store, lessons=0)
        text = record("lesson", "L-long", origin=["E-00000"], scope=["日本" * 5000],
                      title='é"\\' * 5000, aliases=["日本" * 3000], domain="nested/domain")
        path = put(self.store, text)
        _, lessons = self.store.snapshot(verify_views=False)
        self.store.reindex(lessons)
        page = self.store.navigation(lessons, "nested/domain")
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["items"][0]["id"], "L-long")
        self.assertEqual(page["items"][0]["preview_truncated"], ["title", "scope", "aliases"])
        self.assertEqual(path.read_bytes(), text.encode("utf-8"))
        self.assertEqual(self.cli("show", "L-long").stdout, text)
        for data, domain, offset in [({}, None, 0), (lessons, "unknown", 0), (lessons, None, 1000)]:
            empty = self.store.navigation(data, domain, offset)
            self.assertEqual(empty["items"], [])
            self.assertEqual(empty["remaining"], 0)
            self.assertIsNone(empty["next_offset"])
        for args in [("--offset", "-1"), ("--limit", "0"), ("--limit", "101"),
                     ("--offset", "bad"), ("--domain", "../escape"), ("--domain", "C:drive"),
                     ("--domain", "nested\\domain"), ("--domain", "")]:
            self.assertNotEqual(self.cli("navigate", *args).returncode, 0, args)
        self.check()

    def long_domain_records(self):
        domain = "/".join(["d" * 200] * 18)
        self.assertEqual(len(domain), 3617)
        texts = [record("lesson", identifier, origin=["E-origin"], domain=domain,
                        title="😀" * 160, scope=["😀" * 159 + c for c in "abc"],
                        tags=["😀" * 159 + c for c in "def"],
                        aliases=["😀" * 159 + c for c in "ghi"])
                 for identifier in ("L-first", "L-second")]
        return domain, texts

    def test_long_domain_preview_adapts_without_changing_identity_or_records(self):
        # Exercise serialization on every OS, even where PATH_MAX prevents
        # creating this otherwise valid Linux-sized canonical path on disk.
        self.publish("episode", "E-origin")
        records, _ = self.store.snapshot()
        domain, texts = self.long_domain_records()
        lessons = {}
        for text in texts:
            meta, body = m.decode(text)
            m.validate_record(meta, body)
            path = self.store.state / "memory/lessons" / domain / meta["id"] / "revisions/0001.md"
            lessons[meta["id"]] = [(meta, body, path)]
        for versions in lessons.values():
            self.store.validate_links(versions[0][0], records, lessons)
        original = copy.deepcopy(lessons)
        single = self.store.navigation({"L-first": lessons["L-first"]}, domain)
        page = self.store.navigation(lessons, domain)
        self.assertEqual(page["total"], 2)
        self.assertEqual(page["remaining"], 1)
        self.assertEqual(page["next_offset"], 1)
        self.assertLessEqual(len((m.NAVIGATION_HEADER + m.navigation_json(page) + m.NAVIGATION_FOOTER).encode("utf-8")), m.NAVIGATION_BYTES)
        # The same full preview fits alone, but cannot fit with continuation.
        unshortened = {**page, "items": single["items"]}
        self.assertGreater(len((m.NAVIGATION_HEADER + m.navigation_json(unshortened) + m.NAVIGATION_FOOTER).encode("utf-8")), m.NAVIGATION_BYTES)
        item = page["items"][0]
        for key in ("id", "revision", "status", "path"):
            self.assertEqual(item[key], single["items"][0][key])
        omitted = {key for key in ("title", "scope", "tags", "aliases") if key not in item}
        self.assertTrue(omitted)
        self.assertEqual(set(item["preview_truncated"]), omitted)
        self.assertEqual([row["id"] for row in self.pages(lessons, domain)], ["L-first", "L-second"])
        self.assertEqual(lessons, original)
        self.assertEqual([m.encode(*versions[0][:2]) for versions in lessons.values()], texts)

    @unittest.skipUnless(sys.platform == "linux", "Long-path filesystem regression runs on Linux; serialization is tested on every OS")
    def test_long_domain_publication_check_and_repair_preserve_accepted_bytes(self):
        self.publish("episode", "E-origin")
        domain, texts = self.long_domain_records()
        with self.store.lock():
            paths = [self.root / self.store.publish(text, 0) for text in texts]
        records, lessons = self.store.snapshot()
        before = migration.protected(m, self.store)
        index = self.store.path(f"memory/lessons/{domain}/INDEX.md")
        self.assertLess(len(old_indexes(self.store, lessons)[index].encode("utf-8")), m.MAX_RECORD)
        self.assertLessEqual(index.stat().st_size, m.NAVIGATION_BYTES)
        page = json.loads(index.read_text(encoding="utf-8").split("```json\n")[1].split("```")[0])
        continued = self.cli(*shlex.split(page["next_command"]))
        self.assertEqual(continued.returncode, 0, continued.stderr)
        self.assertEqual([r["id"] for r in json.loads(continued.stdout)["items"]], ["L-second"])
        self.check()
        index.unlink()
        repaired = self.cli("reindex", "--repair")
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.check()
        self.assertEqual(migration.protected(m, self.store), before)
        self.assertEqual([p.read_bytes() for p in paths], [text.encode("utf-8") for text in texts])

    def test_leading_hyphen_domain_continuation_runs_verbatim(self):
        self.publish("episode", "E-origin")
        for number in range(2):
            self.publish("lesson", f"L-hyphen-{number}", domain="-legacy",
                         origin=["E-origin"], scope=["fixture"])
        result = self.cli("navigate", "--domain=-legacy", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        first = json.loads(result.stdout)
        continued = self.cli(*shlex.split(first["next_command"]))
        self.assertEqual(continued.returncode, 0, continued.stderr)
        second = json.loads(continued.stdout)
        self.assertEqual([row["id"] for row in first["items"] + second["items"]],
                         ["L-hyphen-0", "L-hyphen-1"])
        self.assertIsNone(second["next_command"])
        self.check()

    def test_missing_indexes_are_reconstructible_not_record_authority(self):
        _, lessons = seed(self.store, lessons=4, domains=2)
        before = migration.protected(m, self.store)
        unknown = self.store.path("memory/lessons/unknown-page.md")
        unknown.write_text("Unknown file; preserve me.\n", encoding="utf-8")
        expected = self.store.indexes(lessons)
        for path in expected:
            path.unlink()
        self.assertNotEqual(self.cli("check").returncode, 0)
        result = self.cli("navigate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["total"], 2)
        self.assertEqual(self.cli("reindex", "--repair").returncode, 0)
        self.check()
        self.assertEqual(migration.protected(m, self.store), before)
        self.assertEqual(unknown.read_text(encoding="utf-8"), "Unknown file; preserve me.\n")
        self.assertNotIn("unknown-page", "".join(expected.values()))
        derived = self.derived()
        with mock.patch.object(m, "write_atomic", wraps=m.write_atomic) as writes:
            self.store.reindex(lessons)
        self.assertEqual(writes.call_count, 0)
        self.assertEqual(self.derived(), derived)

    def test_oversized_old_index_source_repair_upgrade_preserves_history_profiles(self):
        _, lessons = seed(self.store, lessons=70, long_metadata=True)
        before = migration.protected(m, self.store)
        for path, text in old_indexes(self.store, lessons).items():
            path.write_text(text, encoding="utf-8")
        # Include an oversized root map from a much larger old domain listing.
        root_index = self.store.path("memory/INDEX.md")
        root_index.write_text("# Old generated map\n" + "old domain\n" * 14000, encoding="utf-8")
        with self.assertRaises(m.MettleError):
            m.install(self.root, [])
        result = self.cli("reindex", "--repair", source=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = m.install(self.root, [], dry_run=True)
        m.install(self.root, [], expected_plan=plan["plan_id"])
        self.assertEqual(migration.protected(m, self.store), before)
        self.check()
        self.assertEqual(self.cli("bootstrap").returncode, 0)
        # Repair must still reject invalid canonical memory, even for navigation.
        canonical = lessons["L-00000"][-1][2]
        canonical.write_text("x" * (m.MAX_RECORD + 1), encoding="utf-8")
        for command in [("reindex", "--repair"), ("navigate",)]:
            result = self.cli(*command, source=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds", result.stderr)

    def test_nonlesson_publications_never_regenerate_or_write_lesson_navigation(self):
        seed(self.store, lessons=6, domains=2)
        before = self.derived()
        with mock.patch.object(self.store, "indexes", side_effect=AssertionError("Unrelated navigation regenerated")):
            self.publish("episode", "E-new")
            self.publish("review", "V-new", lesson="L-00000", lesson_revision=1,
                         episodes=["E-new"], assessment="counterexample")
            self.publish("reconciliation", "C-new", inputs=["L-00000@1"], evidence=["V-new"], operation="REVISE")
        self.assertEqual(self.derived(), before)
        self.check()

    def test_revision_writes_only_affected_changed_views(self):
        _, lessons = seed(self.store, lessons=6, domains=2)
        self.publish("reconciliation", "C-revise", inputs=["L-00000@1"], evidence=[], operation="REVISE")
        before = self.derived()
        meta, body, path = lessons["L-00000"][-1]
        revised = copy.deepcopy(meta)
        revised.update(revision=2, reconciliations=["C-revise"], title="Changed navigation preview")
        with self.store.lock():
            self.store.publish(m.encode(revised, body), 1)
        changed = {p for p, value in self.derived().items() if value != before.get(p)}
        self.assertEqual(changed, {path.parent.parent / "current.md", self.store.path("memory/lessons/domain-0000/INDEX.md")})
        self.assertEqual(path.read_text(encoding="utf-8"), m.encode(meta, body))
        self.check()

    def test_new_lesson_beyond_preview_leaves_identical_domain_index_unwritten(self):
        seed(self.store, lessons=55)
        before = self.derived()
        self.publish("lesson", "L-zz-new", domain="domain-0000", origin=["E-00000"], scope=["fixture"])
        # Count/remaining changes still update the index, but an unchanged full
        # reindex or refresh performs no redundant writes.
        _, lessons = self.store.snapshot()
        self.assertNotEqual(self.derived()[self.store.path("memory/INDEX.md")], before[self.store.path("memory/INDEX.md")])
        with mock.patch.object(m, "write_atomic", wraps=m.write_atomic) as writes:
            self.store.refresh_lesson(lessons, "L-zz-new")
        self.assertEqual(writes.call_count, 0)
        self.publish("reconciliation", "C-hidden", inputs=["L-zz-new@1"], evidence=[], operation="REVISE")
        meta, body, path = lessons["L-zz-new"][-1]
        revised = {**meta, "revision": 2, "reconciliations": ["C-hidden"]}
        before = self.derived()
        with self.store.lock():
            self.store.publish(m.encode(revised, body + "\nBody-only correction outside navigation."), 1)
        self.assertEqual({p for p, value in self.derived().items() if value != before[p]}, {path.parent.parent / "current.md"})
        self.check()

    def test_interrupted_maintenance_repair_and_unchanged_workspace_retry(self):
        seed(self.store, lessons=3)
        with self.store.lock():
            identifier = w.start(m, self.store, "Synthetic publication", "fixture")["id"]
            text = record("lesson", "L-interrupted", origin=["E-00000"], scope=["fixture"], domain="new-domain")
            draft = self.root / w.make_draft(m, self.store, identifier, text)["draft"]
        before = self.derived()
        real_write = m.write_atomic
        def fail_index(path, text, **kwargs):
            if path.name == "INDEX.md" and "memory" in path.parts:
                raise OSError("synthetic derived maintenance interruption")
            return real_write(path, text, **kwargs)
        with self.store.lock(), mock.patch.object(m, "write_atomic", side_effect=fail_index):
            with self.assertRaisesRegex(OSError, "synthetic"):
                w.publish(m, self.store, draft, 0)
        _, lessons = self.store.snapshot()
        accepted = lessons["L-interrupted"][-1][2]
        self.assertEqual(accepted.read_bytes(), text.encode("utf-8"))
        self.assertNotEqual(self.cli("check").returncode, 0)
        self.assertEqual(self.cli("reindex", "--repair").returncode, 0)
        with self.store.lock():
            w.publish(m, self.store, draft, 0)
            w.publish(m, self.store, draft, 0)
        self.assertEqual(accepted.read_bytes(), text.encode("utf-8"))
        for path, value in before.items():
            if path.name == "current.md":
                self.assertEqual(self.derived()[path], value)
        self.assertEqual(len(w.read_work(m, self.store, identifier)[0]["publications"]), 1)
        self.check()

    def test_reference_retrieval_parity_and_relationship_operation_counts(self):
        seed(self.store, episodes=120, lessons=80, domains=2)
        self.publish("episode", "E-correction", corrects=["E-00000", "E-00001"])
        for identifier, assessment in [("V-incorporated", "counterexample"), ("V-pending", "counterexample"), ("V-support", "support")]:
            self.publish("review", identifier, lesson="L-00000", lesson_revision=1,
                         episodes=["E-00001"], assessment=assessment)
        _, lessons = self.store.snapshot()
        for number, status in enumerate(["active", "contested", "retired", "superseded"]):
            identifier = f"L-{number:05d}"
            self.publish("reconciliation", f"C-{number}", inputs=[identifier + "@1"], evidence=[], operation="REVISE")
            meta, body, _ = lessons[identifier][-1]
            revised = {**meta, "revision": 2, "status": status, "reconciliations": [f"C-{number}"]}
            if number == 0:
                revised.update(support=["V-support"], counterevidence=["V-incorporated"])
            if status == "superseded":
                revised["superseded_by"] = ["L-00004"]
            with self.store.lock():
                self.store.publish(m.encode(revised, body), 1)
        records, lessons = self.store.snapshot()
        with self.store.lock():
            work_id = w.start(m, self.store, "Synthetic rejection", "fixture")["id"]
            w.reject_candidate(m, self.store, work_id, "L-00000@2", ["amberwidget"], "Different applicability.")
        cases = [(kind, query, scope, work) for kind in ["lessons", "episodes"]
                 for query in [["amberwidget"], ["needle00000"], ["source", "of", "truth"], ["source"], ["absentterm"]]
                 for scope, work in [(None, None), ("component/0", None), (None, work_id)]]
        w.retrieve(m, self.store, ["amberwidget"], 3, None)  # Warm a real, verified catalogue.
        for kind, query, scope, work in cases:
            with self.subTest(kind=kind, query=query, scope=scope, work=work):
                expected_records = CountingRecords(records)
                with mock.patch.object(self.store, "snapshot", return_value=(expected_records, lessons)):
                    expected = retrieve_reference(m, self.store, query, 3, scope, kind, work)
                with mock.patch.object(self.store, "snapshot", wraps=self.store.snapshot) as snapshots:
                    actual = w.retrieve(m, self.store, query, 3, scope, kind, work)
                self.assertEqual(actual, expected)
                self.assertEqual(snapshots.call_count, 0)
                if query == ["amberwidget"] and scope is None and work is None:
                    matches = 78 if kind == "lessons" else 121
                    self.assertEqual(expected_records.visits, matches * len(records))
        selected = m.search(self.store, ["needle00000"], 3, None)
        self.assertEqual(selected[0]["pending_counterevidence"], ["V-pending"])
        self.assertEqual(m.search(self.store, ["needle00000"], 3, None, "episodes")[0]["corrected_by"], ["E-correction"])
        statuses = {r["status"] for r in m.search(self.store, ["amberwidget"], 50, None)}
        self.assertEqual(statuses, {"active", "contested", "proposed"})
        with self.store.lock():
            w.update(m, self.store, work_id, "paused", "Changed situation.")
            w.update(m, self.store, work_id, "open", "New applicability context.")
        self.assertEqual(m.search(self.store, ["amberwidget"], 3, None, work_id=work_id),
                         m.search(self.store, ["amberwidget"], 3, None))


if __name__ == "__main__":
    unittest.main()
